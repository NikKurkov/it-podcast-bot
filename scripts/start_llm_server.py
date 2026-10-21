"""Start a local model server with a bounded systemd user cgroup."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from urllib.parse import urlsplit

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config.settings import settings

UNIT = "it-podcast-bot-ollama.service"


def resource_properties() -> list[str]:
    memory = settings.ollama_memory_max_mb
    return [
        f"MemoryMax={memory}M",
        f"MemoryHigh={memory * 19 // 20}M",
        f"MemorySwapMax={settings.ollama_swap_max_mb}M",
        "OOMScoreAdjust=500",
        "OOMPolicy=stop",
    ]


def server_environment(cpu: bool = False) -> dict[str, str]:
    parsed = urlsplit(settings.llm_base_url)
    if (
        parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
        or parsed.scheme != "http"
        or parsed.username
        or parsed.password
        or parsed.port is None
    ):
        raise ValueError(
            "The local launcher requires a loopback HTTP LLM_BASE_URL with an explicit port and without credentials."
        )
    env = os.environ.copy()
    host = parsed.hostname
    if ":" in host:
        host = f"[{host}]"
    env.update(
        OLLAMA_HOST=f"{host}:{parsed.port or 11434}",
        OLLAMA_CONTEXT_LENGTH=str(settings.ollama_context_length),
        OLLAMA_NUM_PARALLEL="1",
        OLLAMA_MAX_LOADED_MODELS="1",
        OLLAMA_NO_CLOUD="true",
        OLLAMA_KEEP_ALIVE="1m",
        LLAMA_ARG_CACHE_RAM=str(settings.ollama_prompt_cache_mb),
        LLAMA_ARG_CTX_CHECKPOINTS=str(settings.ollama_context_checkpoints),
        LLAMA_ARG_CHECKPOINT_MIN_SPACING_NT=str(settings.ollama_checkpoint_min_step),
    )
    if settings.local_llm_engine == "llamacpp":
        if not settings.llm_api_key or settings.llm_api_key == "ollama":
            raise ValueError("Configure a private LLM_API_KEY for the native local server.")
        env["LLAMA_API_KEY"] = settings.llm_api_key
        library = settings.llama_cpp_backend_library
        if library and not cpu:
            if not Path(library).is_file():
                raise ValueError("Configured native backend library is missing.")
            env["GGML_BACKEND_PATH"] = str(Path(library).resolve())
            env["LD_LIBRARY_PATH"] = os.pathsep.join(
                filter(
                    None,
                    [
                        str(Path(library).resolve().parent),
                        str(Path(resolve_executable()).parent),
                        env.get("LD_LIBRARY_PATH"),
                    ],
                )
            )
    if cpu:
        env.pop("GGML_BACKEND_PATH", None)
        env["CUDA_VISIBLE_DEVICES"] = ""
        env["GGML_VK_VISIBLE_DEVICES"] = ""
        env["OLLAMA_VULKAN"] = "false"
    return env


def resolve_executable() -> str:
    native = settings.local_llm_engine == "llamacpp"
    local = PROJECT_ROOT / (
        "data/runtime/ollama/lib/ollama/llama-server"
        if native
        else "data/runtime/ollama/bin/ollama"
    )
    configured = settings.llama_cpp_executable if native else settings.ollama_executable
    name = "llama-server" if native else "ollama"
    candidate = configured or (str(local) if local.is_file() else name)
    path = shutil.which(candidate)
    if path is None:
        relative = PROJECT_ROOT / candidate
        if relative.is_file() and os.access(relative, os.X_OK):
            path = str(relative)
    if path is None:
        raise RuntimeError("The configured local model-server executable is missing.")
    return path


def server_command(cpu: bool = False) -> list[str]:
    executable = resolve_executable()
    if settings.local_llm_engine == "ollama":
        return [executable, "serve"]
    model = Path(settings.llama_cpp_model_path or "").expanduser()
    if not model.is_file():
        raise ValueError("Configure LLAMA_CPP_MODEL_PATH with a complete local GGUF model.")
    parsed = urlsplit(settings.llm_base_url)
    command = [
        executable,
        "--model",
        str(model.resolve()),
        "--alias",
        settings.llm_model,
        "--host",
        parsed.hostname or "127.0.0.1",
        "--port",
        str(parsed.port or 11434),
        "--ctx-size",
        str(settings.ollama_context_length),
        "--parallel",
        "1",
        "--reasoning-budget",
        str(settings.llama_cpp_reasoning_budget),
        "--reasoning-format",
        "deepseek",
        "--cache-ram",
        str(settings.ollama_prompt_cache_mb),
        "--ctx-checkpoints",
        str(settings.ollama_context_checkpoints),
        "--checkpoint-min-step",
        str(settings.ollama_checkpoint_min_step),
        "--sleep-idle-seconds",
        str(settings.llama_cpp_idle_sleep_seconds),
        "--jinja",
        "--no-webui",
    ]
    if settings.llama_cpp_chat_template_file is not None:
        template = Path(settings.llama_cpp_chat_template_file).expanduser()
        if not template.is_file():
            raise ValueError("Configured native chat template file is missing.")
        command += ["--chat-template-file", str(template.resolve())]
    if settings.llama_cpp_threads is not None:
        command += [
            "--threads",
            str(settings.llama_cpp_threads),
            "--threads-batch",
            str(settings.llama_cpp_threads),
        ]
    if cpu:
        command += ["--n-gpu-layers", "0"]
    else:
        if settings.llama_cpp_gpu_layers is not None:
            command += ["--n-gpu-layers", str(settings.llama_cpp_gpu_layers)]
        if settings.llama_cpp_device != "auto":
            command += ["--device", settings.llama_cpp_device]
    return command


def wait_until_ready(*, client: httpx.Client | None = None, timeout: float = 120) -> None:
    parsed = urlsplit(settings.llm_base_url)
    if (
        parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
        or parsed.scheme != "http"
        or parsed.username
        or parsed.password
        or parsed.port is None
    ):
        raise ValueError(
            "Readiness checks require the configured loopback HTTP server with an explicit port."
        )
    if client is None:
        with httpx.Client(trust_env=False, timeout=3) as local_client:
            return wait_until_ready(client=local_client, timeout=timeout)
    native = settings.local_llm_engine == "llamacpp"
    endpoint = f"{parsed.scheme}://{parsed.netloc}" + ("/health" if native else "/api/version")
    headers = {"Authorization": "Bearer " + settings.llm_api_key} if native else {}
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            response = client.get(endpoint, headers=headers)
            if response.status_code == 200:
                return
            if response.status_code != 503:
                raise RuntimeError(f"Local model readiness failed: HTTP {response.status_code}.")
        except (httpx.ConnectError, httpx.TimeoutException):
            pass
        time.sleep(0.2)
    raise RuntimeError("Local model server did not become ready before the startup deadline.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--foreground",
        action="store_true",
        help="Exec the server inside an existing bounded service.",
    )
    parser.add_argument("--cpu", action="store_true", help="Explicit CPU-only mode.")
    parser.add_argument(
        "--stop", action="store_true", help="Stop only the server started by this launcher."
    )
    parser.add_argument(
        "--wait-ready", action="store_true", help="Wait for the owned local API to finish startup."
    )
    args = parser.parse_args()
    if args.wait_ready:
        wait_until_ready()
        return
    if args.foreground:
        os.chdir(PROJECT_ROOT)
        command = server_command(args.cpu)
        os.execvpe(command[0], command, server_environment(args.cpu))
    if args.stop:
        subprocess.run(["systemctl", "--user", "stop", UNIT], check=True)
        return
    # Reuse an installed scheduler dependency, retaining a single server/port.
    fragment = subprocess.run(
        ["systemctl", "--user", "show", UNIT, "-p", "FragmentPath", "--value"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if fragment and not args.cpu:
        limits = [value for value in resource_properties() if value.startswith("Memory")]
        subprocess.run(
            ["systemctl", "--user", "set-property", "--runtime", UNIT, *limits], check=True
        )
        subprocess.run(["systemctl", "--user", "start", UNIT], check=True)
    else:
        # There is no uncapped fallback when the user manager is absent.
        command = ["systemd-run", "--user"]
        command += ["--scope"] if args.cpu else [f"--unit={UNIT}", "--collect"]
        command += [
            f"--property={value}"
            for value in resource_properties()
            if not args.cpu or value.startswith("Memory")
        ]
        command += [
            str(PROJECT_ROOT / ".venv/bin/python"),
            str(Path(__file__).resolve()),
            "--foreground",
        ]
        if args.cpu:
            command.append("--cpu")
        subprocess.run(command, check=True)
        if args.cpu:
            return
    subprocess.run(
        [
            "systemctl",
            "--user",
            "show",
            UNIT,
            "-p",
            "ActiveState",
            "-p",
            "MemoryMax",
            "-p",
            "MemorySwapMax",
        ],
        check=True,
    )


if __name__ == "__main__":
    main()

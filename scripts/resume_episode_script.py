"""Resume a local script from its immutable sources and matching scene checkpoints."""

import argparse
import json
import logging
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config.settings import settings
from app.llm.scriptwriter import rewrite_chunked_dialogue_script_draft
from app.pipeline.episode_paths import resolve_episode_path
from app.pipeline.episode_history import is_published_episode
from app.podcast.script_quality import postprocess_dialogue_script, write_script_quality_report
from app.utils.locking import exclusive_lock


def resume_script(
    path: Path, *, model: str | None = None, target_minutes: float | None = None
) -> Path:
    with exclusive_lock(path / ".package.lock", "This episode package is busy."):
        if (
            is_published_episode(path)
            or (path / "telegram_publish.json").exists()
            or (path / "audio.mp3").exists()
        ):
            raise ValueError(
                "Resume requires an unpublished package without finished audio. Copy it for a new draft."
            )
        blocks = json.loads((path / "source_blocks.json").read_text(encoding="utf-8"))
        if (
            not isinstance(blocks, list)
            or not blocks
            or any(not isinstance(block, str) or not block.strip() for block in blocks)
        ):
            raise ValueError("A complete nonempty source_blocks.json list is required.")
        parameters_path = path / "script_generation.json"
        parameters = (
            json.loads(parameters_path.read_text(encoding="utf-8"))
            if parameters_path.exists()
            else {}
        )
        if not isinstance(parameters, dict):
            raise ValueError("Invalid script_generation.json.")
        parameters.update(
            model=model or parameters.get("model") or settings.llm_chunked_model,
            target_minutes=target_minutes
            or parameters.get("target_minutes")
            or settings.podcast_target_minutes,
        )
        parameters.setdefault("chunk_size", settings.llm_script_chunk_size)
        parameters.setdefault("with_plan", settings.llm_episode_plan_enabled)
        parameters.setdefault("with_review", settings.llm_script_editor_enabled)
        parameters_path.write_text(
            json.dumps(parameters, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        text, validation = rewrite_chunked_dialogue_script_draft(
            (path / "script_draft.md").read_text(encoding="utf-8"),
            **parameters,
            source_blocks=blocks,
            checkpoint_dir=path / "script_scenes",
        )
        if validation.has_structural_blocking_issues:
            raise ValueError(
                "Resumed script failed structural validation; audio was not generated."
            )
        result = postprocess_dialogue_script(text, target_minutes=parameters["target_minutes"])
        output = path / "llm_script.md"
        temporary = output.with_suffix(".tmp")
        temporary.write_text(result.script_text + "\n", encoding="utf-8")
        temporary.replace(output)
        write_script_quality_report(result.report, path / "script_quality_report.json")
        return output


def main():
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--episode", required=True, help="Existing package path; source files are required."
    )
    parser.add_argument(
        "--model", help="Override the saved model; mismatched checkpoints are regenerated."
    )
    parser.add_argument("--target-minutes", type=float)
    args = parser.parse_args()
    if args.target_minutes is not None and args.target_minutes <= 0:
        parser.error("--target-minutes must be positive")
    output = resume_script(
        resolve_episode_path(args.episode, PROJECT_ROOT),
        model=args.model,
        target_minutes=args.target_minutes,
    )
    print(f"Script ready: {output}")
    print(
        "No audio or Telegram publication performed. Render explicitly with scripts/render_episode_audio.py."
    )


if __name__ == "__main__":
    main()

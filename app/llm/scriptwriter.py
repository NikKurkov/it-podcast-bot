from pathlib import Path

from app.config.settings import settings
from app.llm.client import create_llm_client
from app.podcast.prompt_context import build_scriptwriter_context
from app.podcast.script_validation import (
    ScriptValidationResult,
    format_validation_report,
    validate_dialogue_script,
)


DEFAULT_SYSTEM_PROMPT = """Ты сценарист русскоязычного IT-подкаста.
Твоя задача: превратить редакторский черновик в живой сценарий выпуска.

Правила:
- не выдумывай факты, даты, цифры и ссылки;
- сохраняй смысл исходных новостей;
- убирай рекламный шум, если он не важен для истории;
- пиши разговорно, но без кликбейта;
- делай структуру: intro, основные новости, короткие новости, outro;
- добавляй плавные переходы между новостями;
- если данных мало, честно оставляй формулировку осторожной.
"""


def rewrite_script_draft(
    draft_text: str,
    model: str | None = None,
    system_prompt: str | None = None,
    temperature: float = 0.4,
) -> str:
    client = create_llm_client()
    response = client.chat.completions.create(
        model=model or settings.llm_model,
        messages=[
            {"role": "system", "content": system_prompt or _load_system_prompt()},
            {"role": "user", "content": draft_text},
        ],
        temperature=temperature,
    )
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("LLM returned an empty script.")

    return content.strip()


def rewrite_dialogue_script_draft(
    draft_text: str,
    model: str | None = None,
    temperature: float = 0.35,
) -> str:
    return rewrite_script_draft(
        draft_text,
        model=model,
        system_prompt=_load_dialogue_system_prompt(),
        temperature=temperature,
    )


def rewrite_validated_dialogue_script_draft(
    draft_text: str,
    model: str | None = None,
    attempts: int = 2,
    temperature: float = 0.35,
) -> tuple[str, ScriptValidationResult]:
    if attempts < 1:
        raise ValueError("attempts must be at least 1")

    last_script_text = ""
    last_validation: ScriptValidationResult | None = None
    for attempt in range(1, attempts + 1):
        attempt_temperature = max(0.15, temperature - ((attempt - 1) * 0.08))
        script_text = rewrite_dialogue_script_draft(
            draft_text,
            model=model,
            temperature=attempt_temperature,
        )
        validation = validate_dialogue_script(script_text)
        if not validation.has_blocking_issues:
            return script_text, validation

        last_script_text = script_text
        last_validation = validation

    report = format_validation_report(last_validation) if last_validation else "validation did not run"
    raise RuntimeError(
        "LLM generated an invalid dialogue script after "
        f"{attempts} attempts.\n{report}\n\nLast script:\n{last_script_text}"
    )


def model_for_profile(profile: str) -> str:
    if profile == "fast":
        return settings.llm_fast_model
    if profile == "final":
        return settings.llm_final_model
    if profile == "default":
        return settings.llm_model

    raise ValueError(f"Unknown LLM profile: {profile}")


def _load_system_prompt() -> str:
    prompt_path = Path("app/llm/prompts/scriptwriter.md")
    if prompt_path.exists() and prompt_path.read_text(encoding="utf-8").strip():
        return _render_prompt_template(prompt_path.read_text(encoding="utf-8").strip())

    return _render_prompt_template(DEFAULT_SYSTEM_PROMPT)


def _load_dialogue_system_prompt() -> str:
    prompt_path = Path("app/llm/prompts/dialogue_scriptwriter.md")
    if prompt_path.exists() and prompt_path.read_text(encoding="utf-8").strip():
        return _render_prompt_template(prompt_path.read_text(encoding="utf-8").strip())

    return _render_prompt_template(DEFAULT_SYSTEM_PROMPT)


def _render_prompt_template(prompt: str) -> str:
    return prompt.format(**build_scriptwriter_context())

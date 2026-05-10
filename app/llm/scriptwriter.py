from pathlib import Path

from app.config.settings import settings
from app.llm.client import create_llm_client
from app.podcast.prompt_context import build_scriptwriter_context
from app.podcast.script_validation import (
    ScriptValidationResult,
    format_validation_report,
    repair_dialogue_script_text,
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


def edit_dialogue_script(
    script_text: str,
    source_draft: str,
    model: str | None = None,
    temperature: float = 0.28,
) -> str:
    editor_input = (
        "Исходный черновик новостей. Это единственный источник фактов:\n"
        f"{source_draft.strip()}\n\n"
        "Диалоговый сценарий для редакторской правки:\n"
        f"{script_text.strip()}\n\n"
        "Верни только улучшенный диалоговый сценарий в формате mark:/nika:/gleb:/artem:."
    )
    return rewrite_script_draft(
        editor_input,
        model=model,
        system_prompt=_load_dialogue_editor_system_prompt(),
        temperature=temperature,
    )


def edit_validated_dialogue_script(
    script_text: str,
    source_draft: str,
    model: str | None = None,
    attempts: int = 2,
    temperature: float = 0.28,
) -> tuple[str, ScriptValidationResult]:
    if attempts < 1:
        raise ValueError("attempts must be at least 1")

    original_validation = validate_dialogue_script(script_text)
    current_script_text = script_text
    last_validation: ScriptValidationResult | None = None
    for attempt in range(1, attempts + 1):
        attempt_temperature = max(0.12, temperature - ((attempt - 1) * 0.06))
        edited_script_text = edit_dialogue_script(
            current_script_text,
            source_draft=source_draft,
            model=model,
            temperature=attempt_temperature,
        )
        validation = validate_dialogue_script(edited_script_text)
        if not validation.has_blocking_issues and not validation.has_quality_retry_issues:
            return edited_script_text, validation

        repaired_script_text = repair_dialogue_script_text(edited_script_text, validation)
        if repaired_script_text != edited_script_text:
            repaired_validation = validate_dialogue_script(repaired_script_text)
            if (
                not repaired_validation.has_blocking_issues
                and not repaired_validation.has_quality_retry_issues
            ):
                return repaired_script_text, repaired_validation
            validation = repaired_validation
            edited_script_text = repaired_script_text

        current_script_text = _append_editor_validation_feedback(
            source_draft=source_draft,
            script_text=script_text,
            edited_script_text=edited_script_text,
            validation=validation,
        )
        last_validation = validation

    if not original_validation.has_blocking_issues:
        return script_text, original_validation

    return script_text, last_validation or original_validation


def rewrite_validated_dialogue_script_draft(
    draft_text: str,
    model: str | None = None,
    attempts: int = 2,
    temperature: float = 0.35,
    allow_quality_fallback: bool = False,
) -> tuple[str, ScriptValidationResult]:
    if attempts < 1:
        raise ValueError("attempts must be at least 1")

    last_script_text = ""
    last_validation: ScriptValidationResult | None = None
    best_script_text = ""
    best_validation: ScriptValidationResult | None = None
    current_draft_text = draft_text
    for attempt in range(1, attempts + 1):
        attempt_temperature = max(0.15, temperature - ((attempt - 1) * 0.08))
        script_text = rewrite_dialogue_script_draft(
            current_draft_text,
            model=model,
            temperature=attempt_temperature,
        )
        validation = validate_dialogue_script(script_text)
        if not validation.has_blocking_issues and not validation.has_quality_retry_issues:
            return script_text, validation
        if not validation.has_blocking_issues:
            best_script_text = script_text
            best_validation = validation
            current_draft_text = _append_validation_feedback(draft_text, validation)
            last_script_text = script_text
            last_validation = validation
            continue

        repaired_script_text = repair_dialogue_script_text(script_text, validation)
        if repaired_script_text != script_text:
            repaired_validation = validate_dialogue_script(repaired_script_text)
            if (
                not repaired_validation.has_blocking_issues
                and not repaired_validation.has_quality_retry_issues
            ):
                return repaired_script_text, repaired_validation
            if not repaired_validation.has_blocking_issues:
                best_script_text = repaired_script_text
                best_validation = repaired_validation
                current_draft_text = _append_validation_feedback(draft_text, repaired_validation)
                last_script_text = repaired_script_text
                last_validation = repaired_validation
                continue

        last_script_text = script_text
        last_validation = validation
        current_draft_text = _append_validation_feedback(draft_text, validation)

    if best_script_text and best_validation:
        return best_script_text, best_validation

    if allow_quality_fallback and last_script_text:
        fallback_script_text = repair_dialogue_script_text(last_script_text, last_validation)
        fallback_validation = validate_dialogue_script(fallback_script_text)
        if not fallback_validation.has_structural_blocking_issues:
            return fallback_script_text, fallback_validation

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


def _append_validation_feedback(draft_text: str, validation: ScriptValidationResult) -> str:
    return (
        f"{draft_text.rstrip()}\n\n"
        "Редакторские замечания к предыдущей попытке. Перепиши сценарий заново, "
        "исправив все пункты ниже, но не добавляя новых фактов:\n"
        f"{format_validation_report(validation)}"
        "\n\n"
        "Как исправлять:\n"
        "- вместо «давайте перейдём» сразу называй следующий факт и его риск;\n"
        "- вместо «как это поможет обычному разработчику» задавай вопрос про конкретный артефакт: "
        "код, API, лимиты, доступы, сборку, данные;\n"
        "- вместо повторов «командам стоит» используй конкретные действия: "
        "проверьте, зафиксируйте, вынесите, заложите, отключите;\n"
        "- не начинай реплики с «Да», «Абсолютно верно», «Интересно»; "
        "сразу добавляй новый смысл;\n"
        "- каждая строка должна начинаться с mark:, nika:, gleb: или artem:; "
        "никаких отдельных строк без диктора;\n"
        "- не дублируй приветствие и не добавляй второе «Добрый день» после rundown;\n"
        "- rundown должен содержать короткие названия тем без многоточий;\n"
        "- финал должен быть практическим выводом и живым прощанием, без благодарностей и общих обещаний."
    )


def _append_editor_validation_feedback(
    source_draft: str,
    script_text: str,
    edited_script_text: str,
    validation: ScriptValidationResult,
) -> str:
    return (
        "Исходный черновик новостей. Не добавляй факты за его пределами:\n"
        f"{source_draft.strip()}\n\n"
        "Изначальный валидный сценарий, который можно использовать как основу:\n"
        f"{script_text.strip()}\n\n"
        "Предыдущая редакторская версия была отклонена:\n"
        f"{edited_script_text.strip()}\n\n"
        "Ошибки редакторской версии:\n"
        f"{format_validation_report(validation)}\n\n"
        "Перепиши редакторскую версию так, чтобы она осталась живой, но строго прошла формат: "
        "только строки mark:/nika:/gleb:/artem:, без текста вне реплик, без самоназываний, "
        "без повторяющихся шаблонов и без новых фактов."
    )


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


def _load_dialogue_editor_system_prompt() -> str:
    prompt_path = Path("app/llm/prompts/dialogue_editor.md")
    if prompt_path.exists() and prompt_path.read_text(encoding="utf-8").strip():
        return _render_prompt_template(prompt_path.read_text(encoding="utf-8").strip())

    return _render_prompt_template(DEFAULT_SYSTEM_PROMPT)


def _render_prompt_template(prompt: str) -> str:
    return prompt.format(**build_scriptwriter_context())

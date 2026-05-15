from pathlib import Path
import re

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
    max_tokens: int | None = None,
) -> str:
    client = create_llm_client()
    request_kwargs = {}
    if max_tokens is not None:
        request_kwargs["max_tokens"] = max_tokens
    response = client.chat.completions.create(
        model=model or settings.llm_model,
        messages=[
            {"role": "system", "content": system_prompt or _load_system_prompt()},
            {"role": "user", "content": draft_text},
        ],
        temperature=temperature,
        timeout=settings.llm_request_timeout_seconds,
        **request_kwargs,
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


def rewrite_chunked_dialogue_script_draft(
    draft_text: str,
    model: str | None = None,
    chunk_size: int | None = None,
    temperature: float = 0.25,
) -> tuple[str, ScriptValidationResult]:
    blocks = _split_news_blocks(draft_text)
    if not blocks:
        return rewrite_validated_dialogue_script_draft(
            draft_text,
            model=model,
            attempts=2,
            temperature=temperature,
            allow_quality_fallback=True,
        )

    chunk_size = max(1, chunk_size or settings.llm_script_chunk_size)
    chunks = [blocks[index : index + chunk_size] for index in range(0, len(blocks), chunk_size)]
    rendered_chunks = []
    for index, chunk_blocks in enumerate(chunks, start=1):
        chunk_text = "\n\n".join(_compact_news_block(block) for block in chunk_blocks)
        try:
            rendered_chunk = rewrite_script_draft(
                _build_chunk_user_prompt(chunk_text, index, len(chunks)),
                model=model,
                system_prompt=_load_dialogue_chunk_system_prompt(),
                temperature=max(0.12, temperature - ((index - 1) * 0.02)),
                max_tokens=650,
            )
        except Exception:
            rendered_chunk = _build_deterministic_chunk_dialogue(chunk_text, index)

        rendered_chunk = _clean_chunk_dialogue(rendered_chunk)
        if not rendered_chunk:
            rendered_chunk = _build_deterministic_chunk_dialogue(chunk_text, index)
        rendered_chunks.append(rendered_chunk)

    script_text = "\n".join(
        [
            *rendered_chunks,
            "mark: На этом всё, это были главные новости на сегодня. "
            "Главный вывод: инструменты меняются быстро, но проверка фактов, доступов и резервных сценариев остаётся за командой.",
            "nika: Хорошего вам дня. Пусть новые штуки помогают, а не превращаются в ещё одну срочную задачу.",
            "gleb: И пусть внешние сервисы сегодня ведут себя прилично. Хотя запасной план я бы всё равно держал рядом.",
            "artem: С вами были Марк, Ника, Глеб и Артём. До новых встреч.",
        ],
    )
    script_text = repair_dialogue_script_text(script_text)
    validation = validate_dialogue_script(script_text)
    if validation.has_blocking_issues:
        script_text = _build_deterministic_dialogue_from_blocks(blocks)
        validation = validate_dialogue_script(script_text)
    return script_text, validation


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


def _split_news_blocks(draft_text: str) -> list[str]:
    chunks = re.split(r"(?m)(?=^###\s+\d+\.\s+)", draft_text)
    return [chunk.strip() for chunk in chunks if chunk.strip().startswith("###")]


def _build_chunk_user_prompt(chunk_text: str, chunk_index: int, chunks_total: int) -> str:
    return (
        f"Блок {chunk_index} из {chunks_total}. Напиши фрагмент разговора по этим новостям.\n\n"
        f"{chunk_text}\n\n"
        "Верни только 4-8 строк диалога. Не делай приветствие и финальное прощание. "
        "Не произноси ссылки и строки Fact lock дословно."
    )


def _clean_chunk_dialogue(script_text: str) -> str:
    allowed = {"mark", "nika", "gleb", "artem"}
    lines = []
    for raw_line in script_text.splitlines():
        line = raw_line.strip()
        match = re.match(r"^(mark|nika|gleb|artem|Mark|Nika|Gleb|Artem)\s*[:：]\s*(.+)$", line)
        if not match:
            continue
        speaker = match.group(1).casefold()
        if speaker not in allowed:
            continue
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", match.group(2)).strip()
        text = re.sub(r"https?://\S+|\b\w+\.(?:me|ru|com|io|dev)/\S+", "", text).strip()
        if text:
            lines.append(f"{speaker}: {text}")
    repaired = repair_dialogue_script_text("\n".join(lines))
    return repaired.strip()


def _build_deterministic_chunk_dialogue(chunk_text: str, chunk_index: int) -> str:
    topics = _extract_fact_topics(chunk_text)
    if not topics:
        return ""

    lines = []
    for index, topic in enumerate(topics):
        topic_index = chunk_index + index - 1
        lines.extend(_build_fallback_topic_scene(topic, topic_index))
    return "\n".join(lines)


def _build_deterministic_dialogue_from_blocks(blocks: list[str]) -> str:
    topics = []
    for block in blocks:
        topics.extend(_extract_fact_topics(block))
    if not topics:
        return ""

    body = []
    for index, topic in enumerate(topics):
        body.extend(_build_fallback_topic_scene(topic, index))
        if index in {1, 5} and index < len(topics) - 1:
            body.append(_fallback_live_moment(index))
    return "\n".join(
        [
            *body,
            "mark: На этом всё, это были главные новости на сегодня. Финальный вывод: держите рядом факты, доступы и запасной план.",
            "nika: Хорошего вам дня. Пусть обновления сегодня будут скучными, в хорошем смысле.",
            "gleb: А если не будут, пусть хотя бы логи не молчат.",
            "artem: С вами были Марк, Ника, Глеб и Артём. До новых встреч.",
        ],
    )


def _build_fallback_topic_scene(topic: dict[str, str], index: int) -> list[str]:
    patterns = [
        (
            "mark",
            "nika",
            "gleb",
            "artem",
            "Первая зацепка",
            "Если убрать витрину, здесь суть такая",
        ),
        (
            "nika",
            "gleb",
            "artem",
            "mark",
            "А вот следующая тема",
            "Я бы перевела это проще",
        ),
        (
            "gleb",
            "artem",
            "nika",
            "mark",
            "Дальше история с подвохом",
            "Сухой остаток из новости",
        ),
        (
            "artem",
            "mark",
            "gleb",
            "nika",
            "Переключаемся на практический риск",
            "Факт, на который я бы смотрел",
        ),
    ]
    lead, responder, skeptic, closer, transition, fact_prefix = patterns[index % len(patterns)]
    return [
        f"{lead}: {transition}: {topic['claim']}.",
        f"{responder}: {fact_prefix}: {topic['fact']}.",
        f"{skeptic}: {_fallback_skeptic_line(index)}",
        f"{closer}: {_fallback_takeaway_line(index)}",
    ]


def _fallback_skeptic_line(index: int) -> str:
    lines = [
        "Красивый анонс сам по себе ничего не гарантирует: проверять придётся реальные ограничения.",
        "Я бы не радовался раньше времени. Обычно боль прячется в доступах, интеграциях и поддержке.",
        "Звучит бодро, но старый вопрос остаётся: кто будет чинить это, когда всё внезапно упрётся в крайний случай.",
        "Тут не хайп важен, а то, насколько команда понимает, где у неё точка отказа.",
    ]
    return lines[index % len(lines)]


def _fallback_takeaway_line(index: int) -> str:
    lines = [
        "Проверьте, какие системы и процессы это реально задевает, а не только как выглядит заголовок.",
        "Зафиксируйте, что меняется для сборки, данных, доступов или пользовательского сценария.",
        "Если тема касается внешнего сервиса, заранее держите обходной маршрут и понятный статус для команды.",
        "Практический смысл простой: меньше догадок, больше проверяемых фактов и наблюдаемости.",
    ]
    return lines[index % len(lines)]


def _fallback_live_moment(index: int) -> str:
    moments = [
        "nika: Секунду, у кого-то клавиатура так щёлкает, будто уже чинят прод. Продолжаем.",
        "gleb: Кхм. Если это был микрофон, то он тоже просит резервный план.",
    ]
    return moments[index % len(moments)]


def _compact_news_block(block: str) -> str:
    title_match = re.search(r"(?m)^###\s+(.+)$", block)
    title = title_match.group(1).strip() if title_match else "news"
    facts = []
    for line in block.splitlines():
        stripped = line.strip()
        if stripped.startswith("- Main claim:") or stripped.startswith("- Allowed fact:"):
            facts.append(stripped)
    if not facts:
        facts = [_shorten_for_dialogue(block, max_chars=400)]
    return "\n".join([f"### {title}", *facts[:5]])


def _extract_fact_topics(chunk_text: str) -> list[dict[str, str]]:
    claims = re.findall(r"(?m)^-\s+Main claim:\s+(.+)$", chunk_text)
    facts = re.findall(r"(?m)^-\s+Allowed fact:\s+(.+)$", chunk_text)
    topics = []
    for index, claim in enumerate(claims):
        fact = facts[index] if index < len(facts) else claim
        topics.append(
            {
                "claim": _shorten_for_dialogue(claim),
                "fact": _shorten_for_dialogue(fact),
            },
        )
    return topics


def _shorten_for_dialogue(text: str, max_chars: int = 180) -> str:
    text = " ".join(text.split()).strip(" .,:;!?—-")
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


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


def _load_dialogue_chunk_system_prompt() -> str:
    prompt_path = Path("app/llm/prompts/dialogue_chunk_scriptwriter.md")
    if prompt_path.exists() and prompt_path.read_text(encoding="utf-8").strip():
        return _render_prompt_template(prompt_path.read_text(encoding="utf-8").strip())

    return _render_prompt_template(DEFAULT_SYSTEM_PROMPT)


def _render_prompt_template(prompt: str) -> str:
    return prompt.format(**build_scriptwriter_context())

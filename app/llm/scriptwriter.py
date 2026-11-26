from pathlib import Path
import json
import logging
import re


from app.config.settings import settings
from app.llm.artifacts import fingerprint, generation_settings, load_checkpoint, save_checkpoint
from app.llm.client import create_llm_client
from app.llm.context_budget import estimate_tokens, output_token_budget
from app.podcast.prompt_context import build_scriptwriter_context
from app.podcast.characters import get_active_character_keys
from app.podcast.script_validation import (
    ScriptValidationResult,
    format_validation_report,
    repair_dialogue_script_text,
    validate_dialogue_script,
)

logger = logging.getLogger(__name__)


DEFAULT_SYSTEM_PROMPT = """Ты сценарист русскоязычного IT-подкаста.
Твоя задача: превратить редакторский черновик в живой сценарий выпуска.

Правила:
- не выдумывай факты, даты, цифры и ссылки;
- сохраняй смысл исходных новостей;
- убирай рекламный шум, если он не важен для истории;
- пиши разговорно, но без кликбейта;
- выбирай ход беседы по содержанию, без обязательной схемы для каждой темы;
- добавляй плавные переходы между новостями;
- если данных мало, честно оставляй формулировку осторожной.
"""


def rewrite_script_draft(
    draft_text: str,
    model: str | None = None,
    system_prompt: str | None = None,
    temperature: float = 0.4,
    max_tokens: int | None = None,
    response_format: dict | None = None,
    response_path: Path | None = None,
    reasoning_effort: str | None = None,
) -> str:
    if settings.local_llm_engine == "llamacpp" and model and model != settings.llm_model:
        raise ValueError("The native single-model server requires its configured LLM_MODEL alias.")
    resolved_prompt = system_prompt or _load_system_prompt()
    input_tokens = estimate_tokens(
        resolved_prompt + draft_text + (str(response_format) if response_format else "")
    )
    available_output = settings.ollama_context_length - input_tokens
    if available_output <= 0:
        raise ValueError(
            "Complete material exceeds model context. Increase OLLAMA_CONTEXT_LENGTH; source was not truncated."
        )
    request_kwargs = {
        "max_tokens": min(
            output_token_budget(max_tokens or 2048, reasoning_effort=reasoning_effort),
            available_output,
        )
    }
    if response_format is not None:
        request_kwargs["response_format"] = response_format
    effective_effort = (
        reasoning_effort if reasoning_effort is not None else settings.llm_reasoning_effort
    )
    if effective_effort and effective_effort.strip():
        request_kwargs["reasoning_effort"] = effective_effort.strip()
    with create_llm_client() as client:
        response = client.chat.completions.create(
            model=model or settings.llm_model,
            messages=[
                {"role": "system", "content": resolved_prompt},
                {"role": "user", "content": draft_text},
            ],
            temperature=temperature,
            timeout=settings.llm_request_timeout_seconds,
            **request_kwargs,
        )
    if response_path is not None:
        response_path.parent.mkdir(parents=True, exist_ok=True)
        response_path.write_text(response.choices[0].message.content or "", encoding="utf-8")
    if getattr(response.choices[0], "finish_reason", None) == "length":
        raise RuntimeError(
            "Model output was truncated by its token/context limit; no partial script accepted."
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
    temperature: float | None = None,
    target_minutes: float | None = None,
    with_plan: bool = False,
    with_review: bool = False,
    checkpoint_dir: Path | None = None,
    source_blocks: list[str] | None = None,
    included_source_indexes: list[int] | None = None,
) -> tuple[str, ScriptValidationResult]:
    temperature = settings.llm_script_temperature if temperature is None else temperature
    model = model or settings.llm_model
    generation = generation_settings(model)
    author_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "dialogue_scene",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["turns"],
                "properties": {
                    "turns": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["speaker", "text"],
                            "properties": {
                                "speaker": {
                                    "type": "string",
                                    "enum": list(get_active_character_keys()),
                                },
                                "text": {"type": "string", "minLength": 1},
                            },
                        },
                    }
                },
            },
        },
    }
    blocks = source_blocks if source_blocks is not None else _split_news_blocks(draft_text)
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
    # Editorial word pace includes room for pauses; actual audio timing is measured later.
    target_words = max(
        1,
        round(
            (target_minutes or settings.podcast_target_minutes)
            * settings.podcast_script_words_per_minute
        ),
    )
    scene_sources = ["\n\n".join(_compact_news_block(block) for block in chunk) for chunk in chunks]
    plans = {}
    if with_plan:
        from app.llm.scene_editor import plan_scenes

        plan_path = checkpoint_dir / "plan.json" if checkpoint_dir else None
        plan_key = fingerprint(
            {
                "sources": scene_sources,
                "generation": generation,
                "profiles": build_scriptwriter_context(),
                "planner": Path(__file__).with_name("scene_editor.py").read_text(encoding="utf-8"),
            }
        )
        cached = load_checkpoint(plan_path, plan_key)
        plans = (
            cached["scenes"]
            if cached and isinstance(cached.get("scenes"), dict)
            else plan_scenes(scene_sources, model=model)
        )
        save_checkpoint(plan_path, plan_key, {"scenes": plans})
    weights = [
        (plans.get(index) or plans.get(str(index)) or {}).get("depth_weight", len(chunk))
        for index, chunk in enumerate(chunks, start=1)
    ]
    # Normalize first to keep even very large finite editorial weights safe.
    largest_weight = max(weights)
    weights = [weight / largest_weight for weight in weights]
    rendered_chunks = []
    accepted_sources = []
    required_speakers = min(2, len(get_active_character_keys()))
    editor_identity = {
        "code": Path(__file__).with_name("scene_editor.py").read_text(encoding="utf-8"),
        "critic_enabled": settings.llm_scene_critic_enabled,
        "critic_reasoning_effort": settings.llm_source_review_reasoning_effort,
        "native_reasoning_budget": settings.llama_cpp_reasoning_budget
        if settings.local_llm_engine == "llamacpp" else None,
    } if with_review else {}
    for index, (chunk_blocks, chunk_text) in enumerate(zip(chunks, scene_sources), start=1):
        first_source_index = (index - 1) * chunk_size
        chunk_words = max(1, round(target_words * weights[index - 1] / sum(weights)))
        plan = plans.get(index) or plans.get(str(index))
        prompt = _build_chunk_user_prompt(
            chunk_text,
            index,
            len(chunks),
            target_words=chunk_words,
            previous_scene=rendered_chunks[-1] if rendered_chunks else "",
            scene_plan=plan,
        )
        system_prompt = _load_dialogue_chunk_system_prompt()
        key = fingerprint(
            {
                "prompt": prompt,
                "system": system_prompt,
                "generation": generation,
                "temperature": temperature,
                "author_protocol": author_format,
            }
        )
        author_path = checkpoint_dir / f"{index:03d}_draft.json" if checkpoint_dir else None
        cached = load_checkpoint(author_path, key)
        logger.info(
            "Generating dialogue scene %s/%s, target %s words%s",
            index,
            len(chunks),
            chunk_words,
            " (checkpoint)" if cached else "",
        )
        feedback = []
        rendered_chunk = cached.get("script") if cached else None
        rendered_chunk = (
            _remove_copied_dialogue(_clean_chunk_dialogue(rendered_chunk), rendered_chunks)
            if isinstance(rendered_chunk, str) else ""
        )
        if not rendered_chunk:
            author_prompt = prompt
            for author_attempt in range(2):
                try:
                    response = rewrite_script_draft(
                        author_prompt,
                        model=model,
                        system_prompt=system_prompt,
                        temperature=temperature,
                        max_tokens=max(400, chunk_words * (10 if not author_attempt else 20)),
                        response_format=author_format,
                        response_path=(
                            author_path.with_suffix(".raw.txt" if not author_attempt else ".retry.raw.txt")
                            if author_path else None
                        ),
                    )
                except RuntimeError as exc:
                    if not str(exc).startswith((
                        "Model output was truncated", "LLM returned an empty script",
                    )):
                        raise
                    author_error = exc
                except ValueError as exc:
                    if not str(exc).startswith("Complete material exceeds model context."):
                        raise
                    author_error = exc
                else:
                    try:
                        draft = _clean_chunk_dialogue(_parse_author_dialogue(response))
                        rendered_chunk = _remove_copied_dialogue(draft, rendered_chunks)
                        if not rendered_chunk:
                            retry = json.loads(prompt)
                            retry["task"] += (
                                " Предыдущий ответ не содержал новых реплик. Начни сразу "
                                "с факта о текущей теме и отвечай только по её источнику."
                            )
                            author_prompt = json.dumps(retry, ensure_ascii=False)
                            raise ValueError("Scene contains no new dialogue.")
                    except ValueError as exc:
                        author_error = exc
                    else:
                        save_checkpoint(author_path, key, {"script": draft})
                        break
                logger.warning(
                    "Rejected draft for scene %s, attempt %s: %s",
                    index, author_attempt + 1, author_error,
                )
            else:
                if not with_review or included_source_indexes is None:
                    raise author_error
                feedback = [{"claim": "", "reason": str(author_error)}]
        if with_review and included_source_indexes is not None and not feedback:
            if len(validate_dialogue_script(rendered_chunk).speakers) < required_speakers:
                feedback = [{"claim": "", "reason": "Сцену читает один ведущий, нужен диалог."}]
        if with_review and not feedback:
            from app.llm.scene_editor import (
                SceneAuditRejected, SceneReviewRejected, audit_scene, review_scene,
            )

            unresolved = []
            context_sources = [*accepted_sources[-2:], chunk_text]
            for attempt in range(1, settings.llm_factcheck_attempts + 2):
                suffix = "" if attempt == 1 else f"_{attempt}"
                audit_path = (
                    checkpoint_dir / f"{index:03d}_factcheck{suffix}.json"
                    if checkpoint_dir
                    else None
                )
                audit = None
                for candidate_source in (
                    "\n\n".join(context_sources[start:])
                    for start in range(len(context_sources))
                ):
                    audit_key = fingerprint(
                        {
                            "source": candidate_source,
                            "script": rendered_chunk,
                            "generation": generation,
                            "editor": editor_identity,
                        }
                    )
                    audit = load_checkpoint(audit_path, audit_key)
                    if audit is None:
                        try:
                            audit = audit_scene(
                                rendered_chunk,
                                candidate_source,
                                model=model,
                                response_path=(
                                    audit_path.with_suffix(".raw.json") if audit_path else None
                                ),
                            )
                        except SceneAuditRejected as exc:
                            if included_source_indexes is None:
                                raise
                            feedback = [{"claim": "", "reason": str(exc)}]
                            break
                        except ValueError as exc:
                            if not str(exc).startswith(
                                "A complete source exceeds model context."
                            ):
                                raise
                            if candidate_source == chunk_text:
                                if included_source_indexes is None:
                                    raise
                                feedback = [{"claim": "", "reason": str(exc)}]
                                break
                            logger.warning(
                                "Scene %s audit context exceeds model window; dropping oldest source",
                                index,
                            )
                            continue
                        save_checkpoint(audit_path, audit_key, audit)
                    source_context = candidate_source
                    break
                if audit is None:
                    break
                feedback = [*audit["unsupported_claims"], *unresolved]
                if not feedback:
                    if included_source_indexes is not None:
                        quotes = {
                            quote for claim in audit["supported_claims"]
                            for quote in claim.get("quotes", [])
                        }
                        if any(not any(quote in block for quote in quotes) for block in chunk_blocks):
                            feedback = [{
                                "claim": "",
                                "reason": "В сцене не подтверждены факты из всех текущих источников.",
                            }]
                    break
                if attempt > settings.llm_factcheck_attempts:
                    break
                logger.warning(
                    "Scene %s needs source corrections, attempt %s/%s",
                    index,
                    attempt,
                    settings.llm_factcheck_attempts,
                )
                review_path = (
                    checkpoint_dir / f"{index:03d}_review{suffix}.json" if checkpoint_dir else None
                )
                review_key = fingerprint(
                    {
                        "source": source_context,
                        "script": rendered_chunk,
                        "generation": generation,
                        "target_words": chunk_words,
                        "feedback": feedback,
                        "editor": editor_identity,
                    }
                )
                review = load_checkpoint(review_path, review_key)
                if review is None:
                    try:
                        review = review_scene(
                            rendered_chunk,
                            source_context,
                            model=model,
                            target_words=chunk_words,
                            feedback=feedback,
                            response_path=review_path.with_suffix(".raw.json") if review_path else None,
                        )
                    except SceneReviewRejected:
                        if included_source_indexes is None:
                            raise
                        logger.warning("Scene %s editor could not apply corrections", index)
                        break
                    save_checkpoint(review_path, review_key, review)
                rendered_chunk = _remove_copied_dialogue(
                    _clean_chunk_dialogue(review["script"]), rendered_chunks,
                )
                if not rendered_chunk:
                    feedback = [{"claim": "", "reason": "Редактор повторил предыдущий разговор."}]
                    break
                unresolved = [
                    {"claim": "", "reason": issue} for issue in review.get("unresolved_issues", [])
                ]
        if with_review and included_source_indexes is not None and not feedback:
            if len(validate_dialogue_script(rendered_chunk).speakers) < required_speakers:
                feedback = [{"claim": "", "reason": "После правки осталась реплика одного ведущего."}]
        if feedback:
            if included_source_indexes is None:
                raise RuntimeError(
                    f"Scene {index} has unresolved editorial issues; see scene review checkpoint."
                )
            recovery_prompt = json.loads(prompt)
            task = (
                "Напиши короткую самостоятельную версию сюжета на 2–4 реплики нескольких "
                "ведущих. Возьми один важный факт из источника и сохрани его оговорки. "
                "Убери недоказанные объяснения, догадки и пересказ других тем. "
            )
            recovery_prompt["required_corrections"] = feedback
            for offset, block in enumerate(chunk_blocks):
                source_index = first_source_index + offset
                recovery_path = (
                    checkpoint_dir / f"{index:03d}_recovery_{offset + 1}.json"
                    if checkpoint_dir else None
                )
                recovery_source = _compact_news_block(block)
                recovery_prompt["source_material"] = recovery_source
                recovery_prompt["previous_scene_for_continuity_only"] = ""
                recovery_prompt["editorial_angle"] = None
                recovery_prompt["task"] = task + (
                    "Это начало выпуска." if not rendered_chunks else "Начни сразу с этой темы."
                )
                if source_index == len(blocks) - 1:
                    recovery_prompt["task"] += " Естественно заверши выпуск."
                short_scene = _recover_scene(
                    recovery_prompt,
                    recovery_source,
                    model=model,
                    system_prompt=system_prompt,
                    author_format=author_format,
                    identity={"generation": generation, "editor": editor_identity},
                    path=recovery_path,
                    previous_scenes=rendered_chunks,
                )
                if short_scene is None:
                    logger.warning(
                        "Skipping story %s after its short version failed verification",
                        source_index + 1,
                    )
                    continue
                logger.info("Using the verified short version of story %s", source_index + 1)
                rendered_chunks.append(short_scene)
                accepted_sources.append(recovery_source)
                included_source_indexes.append(source_index)
            continue
        rendered_chunks.append(rendered_chunk)
        accepted_sources.append(chunk_text)
        if included_source_indexes is not None:
            included_source_indexes.extend(
                range(first_source_index, first_source_index + len(chunk_blocks))
            )

    if not rendered_chunks:
        raise RuntimeError("No source-verified scenes remain; see scene review checkpoints.")
    script_text = repair_dialogue_script_text("\n".join(rendered_chunks))
    validation = validate_dialogue_script(
        script_text, require_all_characters=False, allowed_speakers=set(get_active_character_keys())
    )
    return script_text, validation


def _recover_scene(
    prompt: dict,
    source: str,
    *,
    model: str,
    system_prompt: str,
    author_format: dict,
    identity: dict,
    path: Path | None,
    previous_scenes: list[str],
) -> str | None:
    from app.llm.scene_editor import audit_scene

    key = fingerprint({
        "prompt": prompt, "system": system_prompt, "protocol": author_format, **identity,
        "previous_scenes": previous_scenes,
    })
    cached = load_checkpoint(path, key)
    if cached is not None:
        return cached["script"]
    try:
        response = rewrite_script_draft(
            json.dumps(prompt, ensure_ascii=False),
            model=model,
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=650,
            response_format=author_format,
            response_path=path.with_suffix(".raw.txt") if path else None,
        )
        script = _remove_copied_dialogue(
            _clean_chunk_dialogue(_parse_author_dialogue(response)), previous_scenes,
        )
        speakers = set(get_active_character_keys())
        validation = validate_dialogue_script(script, allowed_speakers=speakers)
        if validation.has_errors or len(validation.speakers) < min(2, len(speakers)):
            return None
        audit = audit_scene(
            script, source, model=model,
            response_path=path.with_suffix(".audit.raw.json") if path else None,
        )
    except ValueError as exc:
        logger.warning("Short scene rejected: %s", exc)
        return None
    except RuntimeError as exc:
        if not str(exc).startswith(("Model output was truncated", "LLM returned an empty script")):
            raise
        logger.warning("Short scene rejected: %s", exc)
        return None
    if audit["unsupported_claims"] or not audit["supported_claims"]:
        return None
    save_checkpoint(path, key, {"script": script})
    return script


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
        f"Верни только улучшенный диалог: ключ участника ({', '.join(get_active_character_keys())}) и двоеточие."
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

    original_validation = validate_dialogue_script(
        script_text, allowed_speakers=set(get_active_character_keys())
    )
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
        validation = validate_dialogue_script(
            edited_script_text, allowed_speakers=set(get_active_character_keys())
        )
        if not validation.has_blocking_issues and not validation.has_quality_retry_issues:
            return edited_script_text, validation

        repaired_script_text = repair_dialogue_script_text(edited_script_text, validation)
        if repaired_script_text != edited_script_text:
            repaired_validation = validate_dialogue_script(
                repaired_script_text, allowed_speakers=set(get_active_character_keys())
            )
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
        validation = validate_dialogue_script(
            script_text, allowed_speakers=set(get_active_character_keys())
        )
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
            repaired_validation = validate_dialogue_script(
                repaired_script_text, allowed_speakers=set(get_active_character_keys())
            )
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
        fallback_validation = validate_dialogue_script(
            fallback_script_text, allowed_speakers=set(get_active_character_keys())
        )
        if not fallback_validation.has_structural_blocking_issues:
            return fallback_script_text, fallback_validation

    report = (
        format_validation_report(last_validation) if last_validation else "validation did not run"
    )
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
        "Сохрани полные факты и существенные оговорки. Исправь формат, устрани повторы, "
        "сделай обмен репликами естественным. Не подменяй факты общими советами."
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
        f"только строки с ключами участников ({', '.join(get_active_character_keys())}), без текста вне реплик, "
        "без повторяющихся шаблонов и без новых фактов."
    )


def _split_news_blocks(draft_text: str) -> list[str]:
    chunks = re.split(r"(?m)(?=^###\s+\d+\.\s+)", draft_text)
    return [chunk.strip() for chunk in chunks if chunk.strip().startswith("###")]


def _build_chunk_user_prompt(
    chunk_text: str,
    chunk_index: int,
    chunks_total: int,
    *,
    target_words: int | None = None,
    previous_scene: str = "",
    scene_plan: dict | None = None,
) -> str:
    word_budget = target_words or 250
    task = (
        "Верни только новые реплики этой сцены: предыдущий разговор не перепечатывай и не редактируй. Напиши обсуждение по содержанию источников. Ориентир объёма новой сцены — "
        f"{max(1, round(word_budget * 0.85))}–{max(1, round(word_budget * 1.15))} слов. "
        "Если содержательного материала меньше, не растягивай его. "
        + (
            "Это начало выпуска. "
            if not previous_scene
            else "Продолжи беседу, не начинай выпуск заново. "
        )
        + (
            "Это последняя сцена; естественно заверши разговор."
            if chunk_index == chunks_total
            else "Далее будет другая тема; не прощайся со слушателями."
        )
    )
    return json.dumps(
        {
            "scene": {"index": chunk_index, "total": chunks_total},
            "source_material": chunk_text,
            "previous_scene_for_continuity_only": _continuity_excerpt(previous_scene),
            "editorial_angle": scene_plan,
            "task": task,
        },
        ensure_ascii=False,
    )


def _clean_chunk_dialogue(script_text: str) -> str:
    lines = []
    seen = set()
    for line in repair_dialogue_script_text(script_text).splitlines():
        key = " ".join(line.replace("：", ":", 1).casefold().split())
        _, _, dialogue = key.partition(":")
        # Keep short reactions and answers to an explicit question.
        if len(dialogue.split()) >= 12 and key in seen and not lines[-1].endswith("?"):
            continue
        seen.add(key)
        lines.append(line)
    return "\n".join(lines)


def _continuity_excerpt(scene: str) -> str:
    lines = [line for line in scene.splitlines() if line.strip()]
    if not lines:
        return ""
    for line in reversed(lines):
        speaker, _, text = line.replace("：", ":", 1).partition(":")
        words = text.split()
        if len(words) >= 6:
            if len(words) > 32:
                return f"{speaker.strip()}: …{' '.join(words[-32:])}"
            return line.strip()
    return lines[-1].strip()


def _remove_copied_dialogue(scene: str, previous_scenes: list[str]) -> str:
    """Remove verbatim exchanges from earlier scenes, preserving standalone reactions."""
    if not previous_scenes:
        return scene

    def turn_keys(lines):
        return [" ".join(line.replace("：", ":", 1).casefold().split()) for line in lines]

    previous_pairs = set()
    for previous in previous_scenes:
        turns = turn_keys(line for line in previous.splitlines() if line.strip())
        previous_pairs.update(zip(turns, turns[1:]))

    lines = [line for line in scene.splitlines() if line.strip()]
    keys = turn_keys(lines)
    copied = set()
    start = None
    for index, turn in enumerate(keys):
        if index + 1 < len(keys) and (turn, keys[index + 1]) in previous_pairs:
            if start is None:
                start = index
        elif start is not None:
            # A short exchange may recur naturally, even when the wording matches.
            if sum(len(key.partition(":")[2].split()) for key in keys[start:index + 1]) >= 12:
                copied.update(range(start, index + 1))
            start = None
    if not copied:
        return scene
    logger.info("Removed %s turns copied from earlier scenes", len(copied))
    return "\n".join(line for index, line in enumerate(lines) if index not in copied)


def _parse_author_dialogue(response: str) -> str:
    payload = json.loads(response)
    if not isinstance(payload, dict) or set(payload) != {"turns"}:
        raise ValueError("Author must return a JSON object containing only turns.")
    turns = payload["turns"]
    if not isinstance(turns, list) or not turns:
        raise ValueError("Author must return a nonempty turns array.")
    lines = []
    for turn in turns:
        if not isinstance(turn, dict) or set(turn) != {"speaker", "text"}:
            raise ValueError("Each author turn must contain only speaker and text.")
        speaker, text = turn["speaker"], turn["text"]
        if not isinstance(speaker, str) or speaker not in get_active_character_keys():
            raise ValueError("Author returned an unknown or inactive speaker.")
        if not isinstance(text, str) or not text.strip() or "\n" in text or "\r" in text:
            raise ValueError("Author turn text must be nonempty and contain no newlines.")
        lines.append(f"{speaker}: {text}")
    return "\n".join(lines)


def _compact_news_block(block: str) -> str:
    # Keep the full source: late caveats can reverse the meaning of a short claim.
    return block.strip()


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

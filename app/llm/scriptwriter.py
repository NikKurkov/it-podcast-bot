from pathlib import Path

from app.config.settings import settings
from app.llm.client import create_llm_client


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
        return prompt_path.read_text(encoding="utf-8").strip()

    return DEFAULT_SYSTEM_PROMPT

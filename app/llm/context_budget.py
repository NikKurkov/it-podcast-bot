"""Approximate context budgets; split collections, never the source itself."""

from app.config.settings import settings


def estimate_tokens(text: str) -> int:
    # Conservative estimate for multilingual text; the server context must match.
    return (len(text.encode("utf-8")) + 1) // 2


def output_token_budget(visible_tokens: int, *, reasoning_effort: str | None = None) -> int:
    effort = (
        (reasoning_effort if reasoning_effort is not None else settings.llm_reasoning_effort or "")
        .strip()
        .lower()
    )
    reserve = (
        settings.llama_cpp_reasoning_budget
        if settings.local_llm_engine == "llamacpp" and effort != "none"
        else 0
    )
    return visible_tokens + reserve


def full_text_batches(items, render, *, overhead="", output_tokens: int = 1200):
    def fits(batch):
        extra = overhead(batch) if callable(overhead) else overhead
        return (
            estimate_tokens(render(batch) + extra) + output_token_budget(output_tokens)
            <= settings.ollama_context_length
        )

    batch = []
    for item in items:
        if not fits([item]):
            raise ValueError(
                "A complete source exceeds model context. Increase OLLAMA_CONTEXT_LENGTH; text was not truncated."
            )
        if batch and not fits([*batch, item]):
            yield batch
            batch = []
        batch.append(item)
    if batch:
        yield batch

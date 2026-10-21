# Architecture

## Morning pipeline

`make podcast` invokes `scripts/make_podcast.py`, then `scripts/final_run.py`:

1. Read configured Telegram channels using an existing authorized Telethon session.
2. Store posts in SQLite with source/message identity and content deduplication.
3. Consider the previous 24 hours, excluding rejected posts and recently covered material.
4. Order the candidate pool by content-neutral engagement, freshness, and configured source weights. A local LLM selects events semantically using `PODCAST_EDITORIAL_BRIEF`.
5. Fetch linked public articles where possible, retaining provenance and complete accepted text. A fetched article is supporting material, not independent confirmation.
6. Export complete original texts in editorial order. Generate conversational scenes with a duration-dependent word budget and configurable `LLM_SCRIPT_TEMPERATURE` (default `0.25`); no canned fallback replaces model failures. The scene author returns a strict JSON `turns` array with an active-speaker enum. Runtime validation rejects missing text, unknown speakers, malformed responses and truncation before checkpointing; accepted turn text remains complete.
7. With editorial review enabled, audit individual statements and their source evidence. This remains the required source-checking stage in the main editorial path. The scene implication critic is a separate experimental opt-in (`LLM_SCENE_CRITIC_ENABLED=false` by default); when enabled, it runs before statement-level evidence lookup. It checks subjects, scope, conditions, causality and claimed verification. Reported unsupported claims trigger targeted replacement of the complete affected turns and another audit; unresolved problems stop generation. Save atomic scene checkpoints. Then validate dialogue structure and report repetition/pacing. Deterministic repairs change whitespace and known speaker-prefix markup only. Scene structure, participants, explanations, and conclusions follow the source material.
8. Prepare a separate `spoken_script.md` using the pronunciation dictionary and optional phonetic model pass, preserving `llm_script.md`. Partition the speech text losslessly for the selected TTS provider, render voices, assemble pauses/transitions, optionally mix quiet music, and inspect audio with ffprobe.
9. Save the episode package and optionally publish when publication is explicitly enabled.

## Boundaries

- `app/telegram_reader/` handles collection; `app/db/` owns SQLAlchemy persistence.
- `app/llm/` owns model requests, context budgeting, and prompts.
- `app/pipeline/` owns orchestration, history, research, and publication metadata.
- `app/podcast/` owns character configuration and structural script validation.
- `app/audio/` owns providers and ffmpeg processing; `app/telegram_publisher/` owns delivery.
- `scripts/` exposes the same components through command-line tools.

## Integrity and failure behavior

All candidate sources reach semantic selection intact, using context-budget and attention-size batches. A final check re-reads the selected original sources so a fabricated editorial brief cannot establish novelty. Multiple batches are compared through their complete editorial briefs. Oversized individual sources fail explicitly; source prefixes are never silently substituted. Context estimates are approximate and the local server must use the configured context size. An output stopped by the model's token limit is rejected.

A short episode is acceptable when useful material is scarce. Neither old topics nor stock discussion are replayed to meet duration. The word-count duration estimate is advisory; rendered audio duration is authoritative. Show-note timestamps are explicitly approximate.

Research uses only links supplied with selected posts, not general web search. Public-address validation, IP-pinned requests, response-size limits, redirect checks, and a worker deadline bound retrieval. A single semantic article container is extracted; hidden templates and independent recommendation articles are excluded. Code, inline text, tables and late caveats remain intact. For each post the first successfully extracted complete article that fits the context budget is accepted. Every remaining URL is recorded too: failed retrievals retain their error, and unrequested links receive `not_fetched` with `primary_source_loaded` or `research_request_budget_exhausted`. Ambiguous or unstructured pages, unavailable pages and oversized supporting material are recorded and omitted from model input, never silently cropped.

The intermediate model planner is experimental and disabled by default; it is not needed for scene generation. When enabled, it receives one complete source block per request, retaining that source's global index. Sources stay separate rather than relying on the model to align several topics with their indices; this does not establish the factual accuracy of the resulting plan. Previous dialogue is separate from factual evidence. Citation IDs are checked against the source index after generation rather than repeating the entire index in the output schema.

The implication critic and statement verifier are model-based checks, not independent factual confirmation. Local 9B experiments accepted unsupported causal explanations and scope expansions despite receiving the complete source. Valid citation IDs establish provenance, not whether a quote entails the entire claim; a clean model verdict does not guarantee truth or complete error detection. The implication critic's precision experiment produced many false alarms on supported paraphrases, so it is disabled by default and remains experimental. Its opt-out does not remove the statement audit. Bounded correction and re-audit make failures reviewable rather than establish a proof of correctness.

Scene checkpoint fingerprints include complete inputs, prompts, profiles, generation settings and editor implementation. Native mode also includes the resolved GGUF path, size and modification time, so changing the physical model under the same alias invalidates previous checkpoints.

The main pipeline has a run lock; generation, recovery, audio rendering and publication share a per-package mutation lock. A confirmed Telegram send is recorded before disconnecting; repeated publication requires `--republish`. A crash between sending and saving the receipt still requires manual reconciliation. SQLite backups use the online backup API, including committed WAL data.

## Local state

`.env`, Telegram sessions, databases, episode packages, demo audio, logs, and backups stay outside Git. Tests use temporary output and isolated databases. Source code, prompts, configuration examples, and development dependencies are versioned.

## Memory policy

The local server uses a user cgroup with explicit RAM/swap limits, one loaded model
and one request at a time. Heavy Make commands use separate bounded scopes with
an elevated OOM score, and the installed pipeline service has its own cgroup.
These limits do not cap an external model server or GPU memory. The local model
is unloaded before speech synthesis. Additional host prompt caches and context
checkpoints are disabled by default; disk scene checkpoints remain available.
`OLLAMA_CONTEXT_CHECKPOINTS=0` disables SWA snapshots; when explicitly enabled,
`OLLAMA_CHECKPOINT_MIN_STEP=8192` controls their minimum spacing. Snapshots consume
additional memory. Any prefill speedup depends on the actual request sequence
and must be measured rather than inferred from these settings.
The optional native llama.cpp mode serves one text-only GGUF with a private API key
and bounded reasoning. All profile aliases must match that model. Its idle sleep
unloads GPU memory without stopping the systemd dependency; the application checks
model identity and sleep state before loading TTS. Ollama mode uses its native
unload API. Neither mechanism controls unrelated servers or desktop GPU usage.
Native mode can use an explicit existing `LLAMA_CPP_CHAT_TEMPLATE_FILE` matching
the model's chat format. Optional `LLAMA_CPP_GPU_LAYERS` and `LLAMA_CPP_THREADS`
control GPU offload and both generation/prompt-processing threads. Unset values
leave those choices to the server; explicit CPU mode forces zero GPU layers.
See the native [host prompt cache](https://github.com/ggml-org/llama.cpp/pull/16391)
and [SWA checkpoints](https://github.com/ggml-org/llama.cpp/pull/15293) implementations.

## Произносимый текст

Перед выгрузкой LLM и запуском озвучки применяются редактируемый словарь и, при `TTS_AUTO_PRONUNCIATION=true`, контекстные фонетические формы оставшихся иностранных имён, фраз и сокращений. Автоматический проход выключен по умолчанию. Соседние иностранные слова обрабатываются как целая фраза; задача модели — фонетическая запись, без перевода, пояснений, новых фактов или смыслового раскрытия аббревиатур.

Явные формы словаря имеют приоритет. Латинские прописные сокращения без гласных читаются по названиям букв детерминированно. В автоматическом проходе русские прописные сокращения без гласных либо без согласных также разбираются по буквам без обращения к модели: `ИИ` становится `и-и`, а не «искусственный интеллект». Произносимые прописные слова не обязаны читаться по буквам.

Модель возвращает формы с исходными ID; проверяются полнота, алфавит и размер служебных ответов. Эти проверки не доказывают фонетическую или смысловую правильность замены. Замены действуют только на зарегистрированные позиции, затем текст снова делится на короткие речевые части. Оригинальный `llm_script.md` не перезаписывается; отдельные `spoken_script.md` и `speech_pronunciation.json` сохраняют вход синтезатора и позволяют проверить фонетические формы.

Состав новых сцен задаётся `PODCAST_PARTICIPANTS` и проверяется после модели. Сохранённые старые сценарии могут использовать любой известный голос. Выбор TTS берётся из конфигурации: общие CLI/Make/scheduler больше не закрепляют XTTS независимо от `.env`.

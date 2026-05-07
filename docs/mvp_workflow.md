# MVP workflow

## 1. Check setup

```bash
make check
```

Use `python scripts/check_setup.py --telegram` when you need to verify the saved
Telegram session.

## 2. Collect posts

```bash
make collect
```

The collector reads channels from `config/channels.txt`, stores text posts in
SQLite, deduplicates by channel and Telegram message id, and refreshes metrics
for already saved posts.

## 3. Inspect data

```bash
make stats
make sources
make list
make rank
make validate
```

Use `scripts/show_post.py --id <id>` to inspect a single post.

## 4. Export digest

```bash
python scripts/make_digest.py --use-exclude-keywords --ranked --limit 20
```

Exports go to `data/episodes/` and are ignored by git.

## 5. Editorial selection

```bash
python scripts/edit_post.py --id 1 --select --category "top news" --note "Good opener"
python scripts/list_selected_posts.py
python scripts/make_script_draft.py
```

This is still a non-LLM workflow: it only structures manually selected posts.

## 6. Local LLM rewrite

```bash
ollama pull qwen2.5:7b-instruct
make ollama-cpu
make llm-check
make llm-script
```

The LLM reads `data/episodes/latest_script.md` and writes
`data/episodes/latest_llm_script.md`.

## 7. Create episode draft

```bash
python scripts/make_episode_draft.py --use-exclude-keywords --limit 10
python scripts/list_episode_drafts.py
```

Episode drafts are local structured snapshots. They do not use LLMs, audio, or
publishing.

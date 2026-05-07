PYTHON := .venv/bin/python

.PHONY: setup test check collect daily final stats sources list selected auto-select show rank csv digest script ollama-cpu llm-check llm-script llm-script-fast llm-script-final audio episode episodes episode-package unprocess validate backup channels

setup:
	python -m venv .venv
	$(PYTHON) -m pip install -r requirements.txt

test:
	$(PYTHON) -m pytest

check:
	$(PYTHON) scripts/check_setup.py

collect:
	$(PYTHON) scripts/collect_posts.py --limit 20

daily:
	$(PYTHON) scripts/daily_run.py --collect-limit 20 --digest-limit 10

final:
	$(PYTHON) scripts/final_run.py --collect-limit 20 --top 5 --with-audio

stats:
	$(PYTHON) scripts/db_stats.py

sources:
	$(PYTHON) scripts/source_report.py

list:
	$(PYTHON) scripts/list_posts.py --limit 10

selected:
	$(PYTHON) scripts/list_selected_posts.py

auto-select:
	$(PYTHON) scripts/auto_select_posts.py --top 5 --reset-existing

show:
	$(PYTHON) scripts/show_post.py --id 1

rank:
	$(PYTHON) scripts/rank_posts.py --limit 50 --top 10

csv:
	$(PYTHON) scripts/export_posts_csv.py --limit 100

digest:
	$(PYTHON) scripts/make_digest.py --limit 50 --format markdown

script:
	$(PYTHON) scripts/make_script_draft.py

ollama-cpu:
	bash scripts/serve_ollama_cpu.sh

llm-check:
	$(PYTHON) scripts/check_llm.py

llm-script:
	$(PYTHON) scripts/make_llm_script.py

llm-script-fast:
	$(PYTHON) scripts/make_llm_script.py --profile fast

llm-script-final:
	$(PYTHON) scripts/make_llm_script.py --profile final

audio:
	$(PYTHON) scripts/make_audio.py

episode:
	$(PYTHON) scripts/make_episode_draft.py --limit 10

episode-package:
	$(PYTHON) scripts/make_episode_package.py --limit 10 --llm-profile final

episodes:
	$(PYTHON) scripts/list_episode_drafts.py

delete-episode:
	$(PYTHON) scripts/delete_episode_draft.py 1 --keep-files

unprocess:
	$(PYTHON) scripts/mark_posts.py unprocessed --all

validate:
	$(PYTHON) scripts/validate_db.py

backup:
	$(PYTHON) scripts/backup_db.py

channels:
	$(PYTHON) scripts/channels.py list

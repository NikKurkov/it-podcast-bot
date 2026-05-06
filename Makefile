PYTHON := .venv/bin/python

.PHONY: setup test check collect daily stats sources list show rank csv digest episode episodes unprocess validate backup channels

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

stats:
	$(PYTHON) scripts/db_stats.py

sources:
	$(PYTHON) scripts/source_report.py

list:
	$(PYTHON) scripts/list_posts.py --limit 10

show:
	$(PYTHON) scripts/show_post.py --id 1

rank:
	$(PYTHON) scripts/rank_posts.py --limit 50 --top 10

csv:
	$(PYTHON) scripts/export_posts_csv.py --limit 100

digest:
	$(PYTHON) scripts/make_digest.py --limit 50 --format markdown

episode:
	$(PYTHON) scripts/make_episode_draft.py --limit 10

episodes:
	$(PYTHON) scripts/list_episode_drafts.py

unprocess:
	$(PYTHON) scripts/mark_posts.py unprocessed --all

validate:
	$(PYTHON) scripts/validate_db.py

backup:
	$(PYTHON) scripts/backup_db.py

channels:
	$(PYTHON) scripts/channels.py list

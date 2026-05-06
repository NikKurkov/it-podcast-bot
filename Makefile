PYTHON := .venv/bin/python

.PHONY: setup test check collect stats list rank digest validate backup channels

setup:
	python -m venv .venv
	$(PYTHON) -m pip install -r requirements.txt

test:
	$(PYTHON) -m pytest

check:
	$(PYTHON) scripts/check_setup.py

collect:
	$(PYTHON) scripts/collect_posts.py --limit 20

stats:
	$(PYTHON) scripts/db_stats.py

list:
	$(PYTHON) scripts/list_posts.py --limit 10

rank:
	$(PYTHON) scripts/rank_posts.py --limit 50 --top 10

digest:
	$(PYTHON) scripts/make_digest.py --limit 50 --format markdown

validate:
	$(PYTHON) scripts/validate_db.py

backup:
	$(PYTHON) scripts/backup_db.py

channels:
	$(PYTHON) scripts/channels.py list

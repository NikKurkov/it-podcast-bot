PYTHON := .venv/bin/python

.PHONY: setup setup-tts setup-xtts test check collect daily final final-silero final-silero-llm final-silero-llm-music final-xtts-llm-music stats sources list selected auto-select show rank csv digest script validate-script ollama-cpu llm-check llm-script llm-dialogue-script llm-script-fast llm-script-final audio audio-silero audio-silero-music audio-xtts audio-xtts-music audio-report tts-sample tts-sample-silero tts-sample-xtts episode episodes episode-package episode-package-silero episode-package-silero-music unprocess validate backup channels clean-generated clean-generated-dry-run

setup:
	bash scripts/setup_env.sh

setup-tts:
	bash scripts/setup_tts_env.sh

setup-xtts:
	bash scripts/setup_xtts_env.sh

test:
	$(PYTHON) -m pytest

check:
	$(PYTHON) scripts/check_setup.py

collect:
	$(PYTHON) scripts/collect_posts.py --limit 20

daily:
	$(PYTHON) scripts/daily_run.py --collect-limit 20 --digest-limit 10

final:
	$(PYTHON) scripts/final_run.py --with-audio

final-silero:
	$(PYTHON) scripts/final_run.py --with-audio --tts-provider silero

final-silero-llm:
	$(PYTHON) scripts/final_run.py --llm-profile final --dialogue-script --with-audio --tts-provider silero

final-silero-llm-music:
	$(PYTHON) scripts/final_run.py --llm-profile final --dialogue-script --with-audio --tts-provider silero --with-music

final-xtts-llm-music:
	TTS_PROVIDER=xtts $(PYTHON) scripts/final_run.py --llm-profile final --dialogue-script --with-audio --tts-provider xtts --with-music

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

validate-script:
	$(PYTHON) scripts/validate_script.py

ollama-cpu:
	bash scripts/serve_ollama_cpu.sh

llm-check:
	$(PYTHON) scripts/check_llm.py

llm-script:
	$(PYTHON) scripts/make_llm_script.py

llm-dialogue-script:
	$(PYTHON) scripts/make_llm_script.py --profile final --dialogue

llm-script-fast:
	$(PYTHON) scripts/make_llm_script.py --profile fast

llm-script-final:
	$(PYTHON) scripts/make_llm_script.py --profile final

audio:
	$(PYTHON) scripts/make_audio.py

audio-silero:
	$(PYTHON) scripts/make_audio.py --provider silero

audio-silero-music:
	$(PYTHON) scripts/make_audio.py --provider silero --with-music

audio-xtts:
	TTS_PROVIDER=xtts $(PYTHON) scripts/make_audio.py --provider xtts

audio-xtts-music:
	TTS_PROVIDER=xtts $(PYTHON) scripts/make_audio.py --provider xtts --with-music

audio-report:
	$(PYTHON) scripts/audio_report.py data/audio/latest_episode.wav data/audio/latest_episode.mp3

tts-sample:
	$(PYTHON) scripts/make_tts_sample.py

tts-sample-silero:
	$(PYTHON) scripts/make_tts_sample.py

tts-sample-xtts:
	TTS_PROVIDER=xtts $(PYTHON) scripts/make_tts_sample.py

episode:
	$(PYTHON) scripts/make_episode_draft.py --limit 10

episode-package:
	$(PYTHON) scripts/make_episode_package.py --limit 10 --llm-profile final

episode-package-silero:
	$(PYTHON) scripts/make_episode_package.py --limit 10 --llm-profile final --dialogue-script --with-audio --tts-provider silero

episode-package-silero-music:
	$(PYTHON) scripts/make_episode_package.py --limit 10 --llm-profile final --dialogue-script --with-audio --tts-provider silero --with-music

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

clean-generated-dry-run:
	$(PYTHON) scripts/clean_workspace.py

clean-generated:
	$(PYTHON) scripts/clean_workspace.py --yes

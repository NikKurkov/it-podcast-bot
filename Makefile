PYTHON := .venv/bin/python
BOUNDED_PYTHON := systemd-run --user --scope --quiet --property=MemoryMax=5G --property=MemoryHigh=4864M --property=MemorySwapMax=256M choom -n 500 -- $(PYTHON)

.PHONY: setup setup-tts setup-xtts test check doctor doctor-telegram collect daily final final-silero final-silero-llm final-silero-llm-music final-xtts-llm-music podcast podcast-generate-and-publish podcast-publish podcast-preview podcast-script podcast-script-check podcast-check podcast-audio podcast-remix podcast-info podcast-scheduler-preview podcast-scheduler-install scheduler-check publish-latest stats sources list selected auto-select show rank csv digest script validate-script ollama ollama-stop ollama-cpu llm-check llm-script llm-dialogue-script llm-script-fast llm-script-final audio audio-silero audio-silero-music audio-xtts audio-xtts-music audio-report voice-report tts-sample tts-sample-silero tts-sample-xtts episode episodes episode-package episode-package-silero episode-package-silero-music unprocess validate backup channels clean-generated clean-generated-dry-run

setup:
	bash scripts/setup_env.sh

setup-tts:
	bash scripts/setup_tts_env.sh

setup-xtts:
	bash scripts/setup_xtts_env.sh

test:
	$(PYTHON) -m pytest

.PHONY: lint
lint:
	$(PYTHON) -m ruff check app scripts tests

check:
	$(PYTHON) scripts/check_setup.py

doctor:
	$(PYTHON) scripts/doctor.py

doctor-telegram:
	$(PYTHON) scripts/doctor.py --telegram

collect:
	$(PYTHON) scripts/collect_posts.py --limit 20

daily:
	$(PYTHON) scripts/daily_run.py --collect-limit 20 --digest-limit 10

final:
	$(BOUNDED_PYTHON) scripts/final_run.py --with-audio

final-silero:
	$(BOUNDED_PYTHON) scripts/final_run.py --with-audio --tts-provider silero

final-silero-llm:
	$(BOUNDED_PYTHON) scripts/final_run.py --llm-profile final --dialogue-script --with-audio --tts-provider silero

final-silero-llm-music:
	$(BOUNDED_PYTHON) scripts/final_run.py --llm-profile final --dialogue-script --with-audio --tts-provider silero --with-music

final-xtts-llm-music:
	TTS_PROVIDER=xtts $(BOUNDED_PYTHON) scripts/final_run.py --llm-profile final --dialogue-script --with-audio --tts-provider xtts --with-music

podcast:
	$(BOUNDED_PYTHON) scripts/make_podcast.py --with-music

podcast-generate-and-publish:
	$(BOUNDED_PYTHON) scripts/make_podcast.py --with-music --publish

podcast-publish:
	$(PYTHON) scripts/publish_latest.py --episode latest

podcast-preview:
	$(BOUNDED_PYTHON) scripts/make_podcast.py --preview --with-music

podcast-script:
	$(BOUNDED_PYTHON) scripts/make_podcast.py --script-only --no-collect

podcast-script-check:
	$(PYTHON) scripts/check_script_quality.py --episode latest --fix

podcast-check:
	$(PYTHON) scripts/podcast_check.py --episode latest

podcast-audio:
	$(BOUNDED_PYTHON) scripts/render_episode_audio.py --episode latest --with-music

podcast-remix:
	$(BOUNDED_PYTHON) scripts/render_episode_audio.py --episode latest --with-music --remix-only

podcast-info:
	$(PYTHON) scripts/episode_info.py --episode latest

podcast-scheduler-preview:
	$(PYTHON) scripts/install_scheduler.py --time 07:00 --dry-run

podcast-scheduler-install:
	$(PYTHON) scripts/install_scheduler.py --time 07:00

scheduler-check:
	$(PYTHON) scripts/scheduler_check.py

publish-latest:
	$(PYTHON) scripts/publish_latest.py --episode latest

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

ollama:
	$(PYTHON) scripts/start_llm_server.py

ollama-stop:
	$(PYTHON) scripts/start_llm_server.py --stop

ollama-cpu:
	$(PYTHON) scripts/start_llm_server.py --cpu

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
	$(BOUNDED_PYTHON) scripts/make_audio.py

audio-silero:
	$(BOUNDED_PYTHON) scripts/make_audio.py --provider silero

audio-silero-music:
	$(BOUNDED_PYTHON) scripts/make_audio.py --provider silero --with-music

audio-xtts:
	TTS_PROVIDER=xtts $(BOUNDED_PYTHON) scripts/make_audio.py --provider xtts

audio-xtts-music:
	TTS_PROVIDER=xtts $(BOUNDED_PYTHON) scripts/make_audio.py --provider xtts --with-music

audio-report:
	$(PYTHON) scripts/audio_report.py data/audio/latest_episode.wav data/audio/latest_episode.mp3

voice-report:
	$(PYTHON) scripts/voice_report.py

tts-sample:
	$(BOUNDED_PYTHON) scripts/make_tts_sample.py

tts-sample-silero:
	$(BOUNDED_PYTHON) scripts/make_tts_sample.py

tts-sample-xtts:
	TTS_PROVIDER=xtts $(BOUNDED_PYTHON) scripts/make_tts_sample.py

episode:
	$(PYTHON) scripts/make_episode_draft.py --limit 10

episode-package:
	$(BOUNDED_PYTHON) scripts/make_episode_package.py --limit 10 --llm-profile final

episode-package-silero:
	$(BOUNDED_PYTHON) scripts/make_episode_package.py --limit 10 --llm-profile final --dialogue-script --with-audio --tts-provider silero

episode-package-silero-music:
	$(BOUNDED_PYTHON) scripts/make_episode_package.py --limit 10 --llm-profile final --dialogue-script --with-audio --tts-provider silero --with-music

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

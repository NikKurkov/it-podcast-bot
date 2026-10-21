# Ручной рабочий процесс

Для полного утреннего выпуска используйте `make podcast-preview` и команды
публикации из README. Ниже — ручной отбор и промежуточные экспорты.
Все команды выполняются из корня репозитория.

## Подготовка и просмотр

```bash
make doctor
make collect
make stats
make sources
make list
make rank
make validate
.venv/bin/python scripts/show_post.py --id 1
```

Сборщик обновляет метрики и изменённые тексты уже известных сообщений.
Для проверки сессии есть `make doctor-telegram`.

## Отбор и экспорт

```bash
.venv/bin/python scripts/edit_post.py --id 1 --select --category "top news"
.venv/bin/python scripts/list_selected_posts.py
.venv/bin/python scripts/make_script_draft.py
.venv/bin/python scripts/make_digest.py --ranked --limit 20
```

Эти команды экспортируют вручную выбранные материалы. Они не выполняют
полный редакторский аудит и не публикуют сообщения.

## Локальная переработка и звук

```bash
make ollama
make llm-check
make llm-script
make audio
```

Результаты находятся в `data/episodes/` и `data/audio/`. Провайдер голоса
берётся из `.env`; исходный текст и подготовленный для TTS текст сохраняются
раздельно. Для пакетного сценария с источниками и проверками используйте
`make podcast-script`, затем `make podcast-audio` и `make podcast-check`.

## Обслуживание

```bash
make scheduler-check
make backup
make clean-generated-dry-run
```

История исключения повторов учитывает опубликованные выпуски; локальные
превью в неё не входят. Очистку сначала проверяйте через dry run.

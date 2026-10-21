from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.llm import news_ranker, scriptwriter
from app.llm.context_budget import full_text_batches
from app.pipeline.scoring import rank_posts, is_similar_to_any_text
from app.pipeline.script_draft import export_script_markdown
from app.podcast.script_quality import postprocess_dialogue_script, quality_gate_allows_tts


def post(post_id, text):
    return SimpleNamespace(
        id=post_id,
        text=text,
        message_date=datetime(2026, 10, 21, tzinfo=timezone.utc),
        views=100,
        forwards=5,
        source_channel=SimpleNamespace(username="source"),
        telegram_message_id=post_id,
        url=None,
    )


@pytest.mark.parametrize(
    "text",
    [
        "mark: Не факт.\nnika: Это так.",
        "nika: Микрофон передаёт данные без согласия владельца.",
        "mark: НеизвестныйВендор сохранил API v3.11, C++ и C#; стоимость 5%.",
        "mark: Откат обязателен только при ошибке; в остальных случаях он не нужен.",
        "nika: Командам стоит проверить данные.\nartem: Командам стоит проверить данные.",
    ],
)
def test_postprocessing_preserves_meaning_and_short_reactions(text):
    result = postprocess_dialogue_script(text)
    assert result.script_text == text
    assert result.report["postprocess"]["changed"] is False


def test_draft_keeps_complete_source_and_editorial_order(tmp_path):
    late = "Только для тестовой среды, запуск не объявлен."
    original = "НовыйВендор сообщил об изменении. " + "Подробности. " * 150 + late
    path = tmp_path / "draft.md"
    export_script_markdown([post(2, original), post(1, "Вторая тема")], path, "Утро")
    text = path.read_text()
    assert original in text
    assert text.index("#2") < text.index("#1")
    assert "Fact lock" not in text


def test_metrics_do_not_assign_relevance_by_vendor_or_keyword():
    texts = [
        "НезнакомаяМарка изменила инструмент",
        "OpenAI изменила инструмент",
        "Crocs изменила инструмент",
    ]
    ranked = rank_posts([post(index, text) for index, text in enumerate(texts)])
    assert len({item.score for item in ranked}) == 1
    assert all(not item.penalties for item in ranked)


def test_same_vendor_does_not_mean_same_event():
    assert not is_similar_to_any_text(
        "Acme изменила лицензию базы данных", ["Acme выпустила оборудование для обработки видео"]
    )


def test_exact_copies_are_detected():
    assert is_similar_to_any_text(
        "Полный исходный текст новости", ["Полный исходный текст новости"]
    )


def test_context_batching_keeps_sources_intact(monkeypatch):
    monkeypatch.setattr(news_ranker.settings, "ollama_context_length", 200)
    items = ["a" * 140, "b" * 140, "c" * 140]
    batches = list(full_text_batches(items, lambda values: "".join(values), output_tokens=20))
    assert [item for batch in batches for item in batch] == items
    assert len(batches) == 2


def test_oversized_source_reports_error_without_crop(monkeypatch):
    monkeypatch.setattr(news_ranker.settings, "ollama_context_length", 100)
    with pytest.raises(ValueError, match="not truncated"):
        list(full_text_batches(["x" * 200], str, output_tokens=20))


def test_ranker_receives_full_tail_and_all_candidates(monkeypatch):
    candidates = rank_posts([post(i, "Новость " + str(i)) for i in range(30)])
    candidates[-1].post.text += " " + "x" * 600 + " Важная оговорка в конце."
    payloads = []

    def reply(payload, **kwargs):
        payloads.append(payload)
        return '{"selected":[]}'

    monkeypatch.setattr(news_ranker, "rewrite_script_draft", reply)
    news_ranker.select_editorial_posts(candidates, limit=5)
    combined = "\n".join(payloads)
    assert "Важная оговорка в конце." in combined
    assert all(f'"id": {i},' in combined for i in range(30))


def test_model_failure_never_becomes_canned_dialogue(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(scriptwriter, "rewrite_script_draft", fail)
    with pytest.raises(RuntimeError, match="model unavailable"):
        scriptwriter.rewrite_chunked_dialogue_script_draft("### 1. Source\nПолная новость")


def test_unknown_speakers_survive_cleanup_and_are_blocked():
    text = "unknown: Привет.\nmark: Новость."
    result = postprocess_dialogue_script(scriptwriter._clean_chunk_dialogue(text))
    assert "unknown:" in result.script_text
    allowed, reasons = quality_gate_allows_tts(result.report)
    assert not allowed and "validation_issues" in reasons


# Previous repair examples now verify lossless processing instead of canned edits.
@pytest.mark.parametrize(
    "text",
    [
        pytest.param(
            "\nartem: Здесь важно проверить токены доступа до релиза.\nmark: Для команды вывод простой: держите факты рядом с планом действий.\nnika: Практический шаг простой: сравните обещание с фактическим ограничением.\n",
            id="test_postprocess_dialogue_script_tightens_editorial_labels",
        ),
        pytest.param(
            "\nmark: Добрый день, сегодня 09 мая, и вы слушаете НикКаст с обзором главных новостей в мире айти. Проверяем риски недели.\nnika: В выпуске: GitHub, Claude и инфраструктура.\ngleb: Ника, выбирай первую тему.\nartem: GitHub требует резервного плана доступа.\nmark: А вот дальше история про безопасность аккаунтов.\nnika: Подожди, здесь важен контроль прав.\ngleb: Красивые кнопки не заменяют аудит.\nartem: Проверьте роли и токены доступа.\nmark: Переключаемся на инфраструктуру.\nnika: Марк, здесь снова вопрос к процессам.\ngleb: Без мониторинга всё узнают из чата.\nartem: Проверьте алерты и план отката.\nnika: Хорошего вам дня и спокойных релизов.\n",
            id="test_postprocess_dialogue_script_inserts_outro_end_marker_before_goodbye",
        ),
        pytest.param(
            "\nmark: Добрый день, сегодня 09 мая, и вы слушаете НикКаст с обзором главных новостей в мире айти. Проверяем риски недели.\nnika: В выпуске: GitHub, Claude и инфраструктура.\ngleb: Ника, выбирай первую тему.\nartem: GitHub требует резервного плана доступа.\nmark: А вот дальше история про безопасность аккаунтов.\nnika: Подожди, здесь важен контроль прав.\ngleb: Красивые кнопки не заменяют аудит.\nartem: Проверьте роли и токены доступа.\nmark: Переключаемся на инфраструктуру.\nnika: Марк, здесь снова вопрос к процессам.\ngleb: Без мониторинга всё узнают из чата.\nartem: Зафиксируйте алерты и план отката.\n",
            id="test_postprocess_dialogue_script_adds_outro_for_long_episode",
        ),
        pytest.param(
            "\nmark: Ника, открываем тему про доступность GitHub.\nnika: Марк, я бы сразу спросила про запасной доступ.\ngleb: Ника, запасной доступ вспоминают обычно после пожара.\nartem: Глеб, здесь важна воспроизводимость сборки.\nmark: Артём, зафиксируем риск для релизов.\nnika: Подожди, Глеб, но это же ломает обычный рабочий день.\ngleb: Марк, рабочий день ломает отсутствие плана.\nartem: Ника, команде нужен простой чеклист.\n",
            id="test_postprocess_dialogue_script_thins_excess_direct_addresses",
        ),
        pytest.param(
            "\nmark: Анонс звучит бодро, но его еще надо проверять: проверять придётся реальные ограничения.\nnika: Витрина красивая, а ограничения всё равно придется смотреть руками: проверять придётся реальные ограничения.\ngleb: Тут не хайп важен, а то, насколько команда понимает, где у неё точка отказа.\nartem: Практический смысл простой: меньше догадок, больше проверяемых фактов и наблюдаемости.\n",
            id="test_postprocess_dialogue_script_smooths_repeated_checking_phrase",
        ),
        pytest.param(
            "\nmark: Тут не хайп важен, а то, насколько команда понимает, где у неё точка отказа.\nnika: Тут не хайп важен, а то, насколько команда понимает, где у неё точка отказа.\ngleb: Практический смысл простой: меньше догадок, больше проверяемых фактов и наблюдаемости.\nartem: Практический смысл простой: меньше догадок, больше проверяемых фактов и наблюдаемости.\n",
            id="test_postprocess_dialogue_script_varies_repeated_stock_sentences",
        ),
        pytest.param(
            "\nmark: Ника, а по-человечески, что это значит для обычных пользователей?\nnika: Ника, а по-человечески, это просто риск для сервиса.\ngleb: Глеб, а по-человечески, запасной план опять забыли.\nartem: Артем, практический вывод для разработчиков и пользователей: проверить доступы.\n",
            id="test_postprocess_dialogue_script_varies_mechanical_phrases_and_self_addresses",
        ),
        pytest.param(
            "\nmark: Добрый день, сегодня двадцать второе мая, и вы слушаете НикКаст с обзором главных новостей в мире айти.\nnika: В выпуске: Flipper One; Anker Liberty.\ngleb: Кхм. Если это был микрофон, то он тоже просит резервный план.\nmark: Короткий сигнал: Anker выпустила флагманские наушники, который обеспе.\nnika: Anker использует ИИ-чип, который обеспечивает более мощное шумоподавление.\nartem: Проверьте, есть ли в новости конкретный API или ограничение.\n",
            id="test_postprocess_dialogue_script_removes_recording_glitches_and_truncated_fragments",
        ),
        pytest.param(
            "\nmark: Добрый день, сегодня девятнадцатое мая, и вы слушаете НикКаст с обзором главных новостей в мире айти.\nnika: В выпуске: Finally... 1 кГц LG готовит первый Full HD-монитор; Факт дня: этим летом россиянам доступно меньше прямых рейсов; Krea 2, которая создаёт.\ngleb: Я видел похожие истории.\nartem: Проверьте доступы и план отката.\n",
            id="test_postprocess_dialogue_script_replaces_weak_rundown_titles",
        ),
        pytest.param(
            "\nmark: Добрый день, сегодня пятнадцатое мая, и вы слушаете НикКаст с обзором главных новостей в мире айти.\nnika: В выпуске: Новый Li Auto L9 Livis официально появится в России во второй половине года Продажи экс; Crocs и Red Bull выпустят коллекцию сабо в виде болидов Формулы-1 Старт продаж заплан.\ngleb: Я видел похожие истории.\nartem: Проверьте доступы и план отката.\n",
            id="test_postprocess_dialogue_script_cleans_truncated_rundown_fragments",
        ),
        pytest.param(
            "\nmark: Добрый день, сегодня девятое мая, и вы слушаете НикКаст с обзором главных новостей в мире айти.\nnika: В выпуске: Discord массово сбоит по всему миру — сервис не запускается. За п...; РКН добрался до GitHub? Сервис отслеживания OONI зафиксировал снижение....\ngleb: Я видел похожие истории.\nartem: Проверьте доступы и план отката.\n",
            id="test_postprocess_dialogue_script_normalizes_ellipsized_rundown",
        ),
        pytest.param(
            "\nmark: Добрый день, сегодня девятое мая, и вы слушаете НикКаст с обзором главных новостей в мире айти.\nmark: Добрый день, сегодня девятое мая, и вы слушаете НикКаст с обзором главных новостей в мире айти.\nartem: это важно для команд. практическое действие: проверить доступы.\n",
            id="test_postprocess_dialogue_script_normalizes_capitalization_and_duplicate_opening",
        ),
        pytest.param(
            "\nmark: Сегодня мы поговорим о GitHub и доступности репозиториев.\nnika: Сегодня в выпуске: GitHub, Claude и инфраструктура.\ngleb: Да, но это уже было. Командам стоит проверить запасной доступ.\nartem: Командам стоит зафиксировать план отката.\n",
            id="test_postprocess_dialogue_script_repairs_and_reports_changes",
        ),
        pytest.param(
            "\nmark: Риск не в анонсе, а в зависимости команды от внешнего сервиса.\n---\nnika: Практический вопрос в том, где запасной путь.\ngleb: Я видел похожие истории.\nartem: Команде нужен план отката и проверка доступа.\n",
            id="test_repair_dialogue_script_text_removes_markdown_separator",
        ),
        pytest.param(
            "\nmark: Переходим к следующей новости — Discord массово сбоит по всему миру.\nnika: Практический вопрос в запасном канале связи.\ngleb: Я видел похожие истории.\nartem: Проверьте коммуникационные fallback-сценарии.\n",
            id="test_repair_dialogue_script_text_rewrites_plain_transition",
        ),
        pytest.param(
            "\nmark: Сегодня мы поговорим о вайбкодинге и его последствиях.\nnika: Интересно, как это влияет на обычного разработчика? Может, он просто перестанет учиться?\ngleb: Да, но это уже было. Вайбкодинг — это новый тренд на старую идею автоматизации.\nartem: Командам стоит проверить качество генерируемого кода перед внедрением.\nmark: Давайте перейдем к следующей новости о снижении доступности GitHub в России.\nnika: А по-человечески? Это как если бы кто-то заблокировал доступ к репозиториям?\ngleb: И это уже было не раз.\nartem: Командам стоит заложить мониторинг доступности в систему оперативного управления.\nmark: На этом наш выпуск подходит к концу. Спасибо за внимание, проверьте состояние сервисов.\n",
            id="test_repair_dialogue_script_text_rewrites_repeated_team_should_phrase",
        ),
        pytest.param(
            "\nmark: Риск не в анонсе, а в зависимости команды от внешнего сервиса.\nnika: Практический вопрос в том, где запасной путь.\ngleb: Я видел похожие истории.\nartem: Команде нужен план отката и проверка доступа.\nmark: Спасибо за внимание!\n",
            id="test_repair_dialogue_script_text_removes_thanks_outro_line",
        ),
        pytest.param(
            "\nmark: Риск не в анонсе, а в зависимости команды от внешнего сервиса.\nnika: До следующего выпуска!\ngleb: Я видел похожие истории.\nartem: Команде нужен план отката и проверка доступа.\n",
            id="test_repair_dialogue_script_text_removes_generic_outro_line",
        ),
        pytest.param(
            "\nmark: Риск не в анонсе, а в зависимости команды от внешнего сервиса.\nnika: А если по-человечески?\ngleb: Я видел похожие истории.\nartem: Команде нужен план отката и проверка доступа. Будем следить за развитием событий.\n",
            id="test_repair_dialogue_script_text_removes_generic_filler_sentence",
        ),
        pytest.param(
            "\nmark: Сегодня смотрим на практический риск.\nnika: А если по-человечески?\ngleb: Я видел похожие истории.\nartem: Здесь важно проверить контроль доступа.\nmark: В следующем этапе мы превратим этот черновик в полноценный сценарий.\nnika: Спасибо за внимание.\n",
            id="test_repair_dialogue_script_text_removes_meta_lines",
        ),
        pytest.param(
            "\nmark: Добрый день, сегодня девятое мая, и вы слушаете НикКаст.\nДобрый день, сегодня девятое мая, и вы слушаете НикКаст.\nnika: В выпуске короткие темы.\ngleb: Я видел похожие истории.\nartem: Практический риск здесь в интеграции.\n",
            id="test_repair_dialogue_script_text_removes_non_dialogue_text",
        ),
        pytest.param(
            "\nmark: Сегодня смотрим на практический риск.\nnika: Я бы перевела это проще: Получите.\ngleb: Факт выглядит оборванным и заканчивается на предлог в.\nartem: Практический риск здесь в интеграции.\n",
            id="test_repair_dialogue_script_removes_tiny_truncated_fragment_line",
        ),
        pytest.param(
            "\nmark: Сегодня мы поговорим о практическом риске GitHub.\nnika: Ника, а по-человечески, что это значит для обычных пользователей?\ngleb: Глеб, а по-человечески, запасной план опять забыли.\nartem: Командам стоит проверить доступы.\nmark: Давайте перейдем к следующей новости о Discord.\nnika: Интересно, как это влияет на обычного разработчика?\ngleb: Да, но это уже было. Командам стоит следить за такими новостями.\nartem: Здесь важно проверить контроль доступа.\n",
            id="test_golden_script_removes_typical_mechanical_phrases",
        ),
    ],
)
def test_previous_editorial_examples_keep_the_complete_text(text):
    expected = "\n".join(line.strip() for line in text.splitlines()).strip()
    assert postprocess_dialogue_script(text).script_text == expected


@pytest.mark.parametrize(
    "text",
    [
        pytest.param(
            "Главное с Google I/O: Gemini получил Omni для видео, Spark для приложений и новые инструменты для разработчиков.",
            id="test_diversify_ranked_posts_skips_product_story_already_in_roundup0",
        ),
        pytest.param(
            "Google отдельно показал Gemini Omni: модель генерирует видео, картинки и интерактивные сцены по описанию.",
            id="test_diversify_ranked_posts_skips_product_story_already_in_roundup1",
        ),
        pytest.param(
            "РКН добрался до GitHub: OONI зафиксировал снижение доступности платформы в России.",
            id="test_diversify_ranked_posts_skips_cross_channel_same_story2",
        ),
        pytest.param(
            "GitHub стал хуже открываться в РФ, сервис OONI пишет о снижении доступности.",
            id="test_diversify_ranked_posts_skips_cross_channel_same_story3",
        ),
        pytest.param(
            "Discord массово сбоит по всему миру, API не отвечает у пользователей.",
            id="test_diversify_ranked_posts_skips_cross_channel_same_story4",
        ),
        pytest.param(
            "Security incident in GitHub production infrastructure",
            id="test_diversify_ranked_posts_limits_one_source_dominance5",
        ),
        pytest.param(
            "Grok чаще других чат-ботов доводит юзеров до психоза. Психолог проверил ИИ и нашёл, что бот поддерживает бредовые идеи.",
            id="test_is_podcast_candidate_rejects_personal_ai_psychology_story6",
        ),
        pytest.param(
            "Google раскатывает новый дизайн для иконок Workspace. Новые значки с градиентом появятся в Gmail, Drive, Docs и Calendar.",
            id="test_is_podcast_candidate_rejects_cosmetic_workspace_icon_update7",
        ),
        pytest.param(
            "Парк юрского периода почти реальность: ученые впервые вырастили живых цыплят из полностью искусственных яиц и хотят вернуть вымершие виды птиц.",
            id="test_is_podcast_candidate_rejects_artificial_bio_story_as_false_ai_positive8",
        ),
        pytest.param(
            "Россияне теперь могут платить рублями в Китае. Оплата по QR-кодам заработала в торговых точках с конвертацией в юани.",
            id="test_is_podcast_candidate_rejects_qr_payment_code_false_positive9",
        ),
        pytest.param(
            "Anker выпустила флагманские наушники soundcore Liberty 5 Pro с ИИ-чипом, шумоподавлением, Bluetooth и дисплеем в кейсе.",
            id="test_is_podcast_candidate_rejects_consumer_ai_gadget_without_engineering_angle10",
        ),
        pytest.param(
            "Осенью начнется рекордное Эль-Ниньо, рост температуры Тихого океана может запустить катаклизмы.",
            id="test_is_podcast_candidate_rejects_climate_and_celebrity_lifestyle_posts11",
        ),
        pytest.param(
            "Работа мечты: Марк Цукерберг ищет спасателя для частного пляжа на острове на Гавайях.",
            id="test_is_podcast_candidate_rejects_climate_and_celebrity_lifestyle_posts12",
        ),
        pytest.param(
            "Становимся топовыми ИИ-инженерами: AI-агенты, вайбкодинг, промпт-инжиниринг и 9 уроков. Изучаем бесплатно по ссылке.",
            id="test_is_podcast_candidate_rejects_promo_course_post13",
        ),
        pytest.param(
            "Google и Samsung показали умные очки, носимая революция ждёт нас осенью",
            id="test_is_podcast_candidate_rejects_wearable_gadget_with_weak_ai_angle14",
        ),
        pytest.param(
            "Промт дня: возвращаем обычный поиск Google без AI Overviews. Сохраняем, работает прямо в поисковой строке браузера.",
            id="test_is_podcast_candidate_rejects_prompt_day_without_engineering_angle15",
        ),
        pytest.param(
            "Разработчики показали prompt-injection атаку на GitHub OAuth flow и выпустили API-патч для production-инфраструктуры.",
            id="test_is_podcast_candidate_rejects_prompt_day_without_engineering_angle16",
        ),
        pytest.param(
            "Яндекс выяснил, каких героев классики школьники чаще зовут в Алисе AI при подготовке к ЕГЭ",
            id="test_is_podcast_candidate_rejects_school_ai_context_without_engineering_angle17",
        ),
        pytest.param(
            "Anthropic выпустила курсы по Claude Code, MCP и навыкам ИИ-разработки для автоматизации рабочих задач",
            id="test_is_podcast_candidate_rejects_school_ai_context_without_engineering_angle18",
        ),
        pytest.param(
            "На Prime Video вышел финал сериала Пацаны, доступны все серии нового сезона",
            id="test_is_podcast_candidate_rejects_streaming_and_series_news19",
        ),
        pytest.param(
            "Crocs и Red Bull выпустят коллекцию сабо в виде болидов Формулы-1",
            id="test_is_podcast_candidate_rejects_consumer_topic_with_weak_ai_angle20",
        ),
        pytest.param(
            "Sony показала ИИ-ассистента для съемки в новых смартфонах Xperia",
            id="test_is_podcast_candidate_rejects_consumer_topic_with_weak_ai_angle21",
        ),
        pytest.param(
            "Subnautica 2 вышла в раннем доступе с новыми биомами",
            id="test_is_podcast_candidate_rejects_non_it_consumer_topic22",
        ),
        pytest.param(
            "OpenAI добавила Codex в мобильное приложение ChatGPT для управления сессиями разработки",
            id="test_is_podcast_candidate_rejects_non_it_consumer_topic23",
        ),
        pytest.param(
            "Новый Li Auto L9 официально появится в России во второй половине года",
            id="test_score_post_breakdown_penalizes_consumer_gadget_news_without_it_angle24",
        ),
        pytest.param(
            "В GitHub Actions добавили AI-проверку supply chain зависимостей для Python API",
            id="test_score_post_breakdown_penalizes_consumer_gadget_news_without_it_angle25",
        ),
        pytest.param(
            "Большой трейлер нового фильма выходит летом",
            id="test_score_post_breakdown_penalizes_non_it_text26",
        ),
        pytest.param(
            "Срочно забираем скидку, жми тут и сохраняем себе",
            id="test_score_post_breakdown_penalizes_low_signal_wording27",
        ),
        pytest.param(
            "Security release fixes Python API vulnerability in production infrastructure",
            id="test_score_post_breakdown_rewards_it_relevance28",
        ),
    ],
)
def test_previous_topic_examples_have_no_keyword_penalties(text):
    item = rank_posts([post(1, text)])[0]
    assert not item.penalties
    assert not item.topics


@pytest.mark.parametrize(
    "text",
    [
        pytest.param(
            "gleb: GitHub снова проверяет терпение команд.",
            id="test_ensure_opening_and_rundown_compacts_long_topic_titles",
        ),
        pytest.param(
            "gleb: GitHub снова проверяет терпение команд.",
            id="test_ensure_opening_and_rundown_uses_short_topic_titles",
        ),
        pytest.param(
            "\ngleb: Я бы перевела это проще: GitHub опять проверяет рабочий процесс.\nartem: Я бы спросила про конкретный механизм отказа.\nnika: Я бы перевел это на человеческий язык.\n",
            id="test_postprocess_dialogue_script_fixes_first_person_gender_agreement",
        ),
        pytest.param(
            "\ngleb: GitHub снова проверяет терпение команд.\nartem: Проверьте зеркала и план отката.\n",
            id="test_ensure_opening_and_rundown_adds_missing_intro",
        ),
        pytest.param(
            "\nnika: А вот следующая тема: Finally.\ngleb: Я бы перевела это проще: 1 кГц LG готовит к выпуску первый Full HD-монитор с поддержкой 1000 Гц.\nartem: Переключаемся на практический риск: Факт дня: этим летом россиянам доступно меньше прямых рейсов.\n",
            id="test_postprocess_dialogue_script_removes_standalone_weak_transition_titles",
        ),
    ],
)
def test_framing_and_grammar_are_not_rewritten_by_phrase_tables(text):
    expected = "\n".join(line.strip() for line in text.splitlines()).strip()
    assert postprocess_dialogue_script(text).script_text == expected


def test_source_label_in_original_text_is_not_deleted():
    source = "### 1. News\nSource: preliminary results; production use is not supported."
    assert scriptwriter._compact_news_block(source) == source


def test_generation_output_budget_fits_remaining_context(monkeypatch):
    captured = {}

    class Client:
        def __enter__(self):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))
            return self

        def __exit__(self, *args):
            pass

        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=' {"turns": [{"speaker": "mark", "text": "Новость."}, {"speaker": "nika", "text": "Понятно."}]}'
                        ),
                        finish_reason="stop",
                    )
                ]
            )

    monkeypatch.setattr(scriptwriter, "create_llm_client", Client)
    scriptwriter.rewrite_chunked_dialogue_script_draft("### 1. Source\nКороткая новость.")
    from app.llm.context_budget import estimate_tokens

    used = estimate_tokens("".join(message["content"] for message in captured["messages"]))
    assert used + captured["max_tokens"] <= scriptwriter.settings.ollama_context_length


def test_ranker_compares_few_winners_across_batches(monkeypatch):
    candidates = rank_posts([post(i, f"Новость {i}") for i in (1, 2)])
    monkeypatch.setattr(
        news_ranker, "full_text_batches", lambda items, *args, **kwargs: [[item] for item in items]
    )
    calls = []

    def choose(items, **kwargs):
        calls.append([item.post.id for item in items])
        return items[:1]

    monkeypatch.setattr(news_ranker, "_choose", choose)
    selected = news_ranker.select_editorial_posts(candidates, limit=5)
    assert [1, 2] in calls
    assert calls[:2] == [[1], [2]]
    assert [item.post.id for item in selected] == [1]


@pytest.mark.parametrize(
    "text",
    [
        pytest.param(
            "\nmark: Риск здесь в цепочке поставки пакета.\nnika: Практический вопрос в том, кто проверяет обновления.\ngleb: Командам стоит не верить красивым словам без плана отката.\nartem: Командам стоит вынести проверку доступа в релизный чеклист.\n",
            id="test_validate_dialogue_script_blocks_repeated_team_should_phrase",
        ),
        pytest.param(
            "\nmark: Риск здесь в цепочке поставки пакета.\nnika: Интересно, как это может повлиять на наши проекты?\ngleb: Абсолютно верно. Я видел похожие истории.\nartem: Здесь важен план отката.\n",
            id="test_validate_dialogue_script_blocks_bland_acknowledgement_lines",
        ),
        pytest.param(
            "\nmark: Риск здесь в цепочке поставки пакета.\nnika: Практический вопрос в том, кто проверяет обновления.\ngleb: Я видел похожие истории.\nartem: Здесь важен план отката.\nmark: На этом наш выпуск подходит к концу.\n",
            id="test_validate_dialogue_script_blocks_generic_closing",
        ),
        pytest.param(
            "\nmark: Риск здесь в цепочке поставки пакета.\nnika: И как это влияет на обычного разработчика?\ngleb: Я видел похожие истории.\nartem: Здесь важен план отката.\n",
            id="test_validate_dialogue_script_blocks_generic_developer_question",
        ),
        pytest.param(
            "\nmark: Давайте перейдём к следующей новости.\nnika: Как это поможет обычному разработчику?\ngleb: Я видел похожие истории.\nartem: Здесь важен план отката.\n",
            id="test_validate_dialogue_script_blocks_repetitive_transition_filler",
        ),
        pytest.param(
            "\nmark: Сегодня мы поговорим о новых бенчмарках.\nnika: Давайте разберём, как это влияет на команды.\ngleb: Я видел похожие истории.\nartem: Здесь важно проверить контроль доступа.\n",
            id="test_validate_dialogue_script_warns_on_broad_intro_filler",
        ),
        pytest.param(
            "\nmark: Сегодня смотрим на практический риск. Что же нас ждёт?\nnika: А если по-человечески?\ngleb: Я видел похожие истории.\nartem: Здесь важно проверить контроль доступа.\n",
            id="test_validate_dialogue_script_warns_on_generic_filler",
        ),
        pytest.param(
            "\nmark: Сегодня смотрим на практический риск.\nnika: А если по-человечески?\ngleb: Я видел похожие истории.\nartem: 这里出现了中文翻译块。\n",
            id="test_validate_dialogue_script_errors_on_unexpected_translation_block",
        ),
        pytest.param(
            "\nmark: Сегодня смотрим на практический риск.\nnika: Я бы перевела это проще: Получите.\ngleb: Факт выглядит оборванным и заканчивается на предлог в.\nartem: Практический риск здесь в интеграции.\n",
            id="test_validate_dialogue_script_blocks_truncated_fragments",
        ),
        pytest.param(
            "\nmark: Сегодня смотрим на практический риск.\nnika: Ника, вот здесь тебе стоит спросить про доступы.\ngleb: Я видел похожие истории.\nartem: Практический риск здесь в интеграции.\n",
            id="test_validate_dialogue_script_blocks_self_address",
        ),
        pytest.param(
            "\nmark: Сегодня смотрим на практический риск.\nnika: А по-человечески, где здесь боль команды?\ngleb: Я видел похожие истории.\nartem: Практический риск здесь в интеграции.\nnika: А по-человечески, кто будет это поддерживать?\n",
            id="test_validate_dialogue_script_blocks_repeated_robotic_questions",
        ),
        pytest.param(
            "\nmark: Сегодня смотрим на практический риск.\ngleb: Звучит отлично. Осталось понять, кто это будет поддерживать.\nnika: А если по-человечески?\nartem: Практический риск здесь в интеграции.\ngleb: Звучит отлично. Осталось понять, кто это будет поддерживать.\n",
            id="test_validate_dialogue_script_errors_on_repeated_overused_phrase",
        ),
        pytest.param(
            "\nmark: Сегодня смотрим на практический риск.\ngleb: Если обещают магию, сначала ищем место, где она будет ломаться.\nnika: А если по-человечески?\nartem: Здесь важно проверить контроль доступа.\n",
            id="test_validate_dialogue_script_errors_on_copied_prompt_example_phrase",
        ),
        pytest.param(
            "\nmark: Давайте восстановим цепочку событий.\ngleb: Я видел похожие истории.\nnika: А если по-человечески?\nartem: Здесь важно проверить контроль доступа.\n",
            id="test_validate_dialogue_script_errors_on_stock_character_phrase",
        ),
        pytest.param(
            "\nmark: На этом всё, в следующий раз мы будем готовы к полноценному сценарию.\ngleb: Я видел похожие истории.\nnika: А если по-человечески?\nartem: Здесь важно проверить контроль доступа.\n",
            id="test_validate_dialogue_script_errors_on_meta_phrase",
        ),
        pytest.param(
            "\nmark: Один.\nmark: Два.\nmark: Три.\ngleb: Три.\nnika: Четыре.\nnika: Пять.\nartem: Шесть.\nartem: Семь.\nartem: Восемь.\n",
            id="test_validate_dialogue_script_blocks_underused_character",
        ),
        pytest.param(
            "\nnika: Практический вопрос в том, где запасной путь.\nmark: Риск не в анонсе, а в зависимости команды от внешнего сервиса.\ngleb: Я видел похожие истории.\nartem: Команде нужен план отката и проверка доступа.\n",
            id="test_validate_dialogue_script_blocks_bad_opening_speaker",
        ),
        pytest.param(
            "\nmark: Риск не в анонсе, а в зависимости команды от внешнего сервиса.\nnika: Auto-selected by final run score=13.58, поэтому эта тема важна.\ngleb: Я видел похожие истории.\nartem: Команде нужен план отката и проверка доступа.\n",
            id="test_validate_dialogue_script_blocks_service_leak",
        ),
        pytest.param(
            "\nmark: Риск не в анонсе, а в зависимости команды от внешнего сервиса.\ngleb: Я видел похожие истории.\nnika: Практический вопрос в том, где запасной путь.\nartem: Команде нужен план отката и проверка доступа.\nmark: В следующем выпуске мы продолжим следить за обновлениями.\n",
            id="test_validate_dialogue_script_blocks_next_episode_outro",
        ),
    ],
)
def test_content_judgments_never_rewrite_or_delete_turns(text):
    expected = "\n".join(line.strip() for line in text.splitlines()).strip()
    assert postprocess_dialogue_script(text).script_text == expected


def test_scene_checkpoint_resumes_without_model_and_invalidates_on_source_change(
    tmp_path, monkeypatch
):
    calls = []

    def generate(*args, **kwargs):
        calls.append(args[0])
        return '{"turns": [{"speaker": "mark", "text": "Новость."}, {"speaker": "nika", "text": "Уточнение."}]}'

    monkeypatch.setattr(scriptwriter, "rewrite_script_draft", generate)
    source = "### 1. Source\nПолная новость"
    first, _ = scriptwriter.rewrite_chunked_dialogue_script_draft(source, checkpoint_dir=tmp_path)
    second, _ = scriptwriter.rewrite_chunked_dialogue_script_draft(source, checkpoint_dir=tmp_path)
    assert first == second and len(calls) == 1
    scriptwriter.rewrite_chunked_dialogue_script_draft(
        source + " Но запуск не объявлен.", checkpoint_dir=tmp_path
    )
    assert len(calls) == 2


def test_unresolved_fact_review_blocks_scene_and_saves_audit(tmp_path, monkeypatch):
    from app.llm import scene_editor

    monkeypatch.setattr(
        scriptwriter,
        "rewrite_script_draft",
        lambda *a, **k: '{"turns": [{"speaker": "mark", "text": "Новость."}]}',
    )
    monkeypatch.setattr(
        scene_editor,
        "audit_scene",
        lambda *a, **k: {
            "supported_claims": [],
            "unsupported_claims": [{"claim": "Новость.", "reason": "Нет подтверждения"}],
        },
    )
    monkeypatch.setattr(
        scene_editor,
        "review_scene",
        lambda *a, **k: {
            "script": "mark: Новость.",
            "changes": [],
            "unresolved_issues": ["Источники противоречат утверждению"],
        },
    )
    with pytest.raises(RuntimeError, match="unresolved editorial"):
        scriptwriter.rewrite_chunked_dialogue_script_draft(
            "### 1. Source\nНовость",
            checkpoint_dir=tmp_path,
            with_review=True,
        )
    assert (tmp_path / "001_draft.json").exists()
    assert (tmp_path / "001_review.json").exists()


def test_default_model_change_invalidates_scene_checkpoint(tmp_path, monkeypatch):
    calls = []

    def generate(*args, **kwargs):
        calls.append(kwargs["model"])
        return '{"turns": [{"speaker": "nika", "text": "Новость."}, {"speaker": "artem", "text": "Уточнение."}]}'

    monkeypatch.setattr(scriptwriter, "rewrite_script_draft", generate)
    monkeypatch.setattr(scriptwriter.settings, "llm_model", "first-model")
    scriptwriter.rewrite_chunked_dialogue_script_draft(
        "### 1. Source\nНовость", checkpoint_dir=tmp_path
    )
    monkeypatch.setattr(scriptwriter.settings, "llm_model", "second-model")
    scriptwriter.rewrite_chunked_dialogue_script_draft(
        "### 1. Source\nНовость", checkpoint_dir=tmp_path
    )
    assert calls == ["first-model", "second-model"]


def test_large_pool_budget_depends_on_current_batch_schema(monkeypatch):
    monkeypatch.setattr(news_ranker.settings, "ollama_context_length", 3200)
    monkeypatch.setattr(news_ranker.settings, "podcast_editorial_brief", "")
    monkeypatch.setattr(news_ranker.Path, "read_text", lambda *a, **k: "editor")
    visited = []

    def choose(items, **kwargs):
        visited.extend(item.post.id for item in items)
        return []

    monkeypatch.setattr(news_ranker, "_choose", choose)
    candidates = rank_posts([post(i, "x") for i in range(500)])
    assert news_ranker.select_editorial_posts(candidates, limit=1) == []
    assert sorted(visited) == list(range(500))


def test_source_headings_cannot_create_additional_stories(tmp_path):
    original = "Новость с примером Markdown:\n### 99. Это текст источника, а не новая новость."
    blocks = export_script_markdown(
        [post(1, original), post(2, "Следующая новость")], tmp_path / "draft.md", "Утро"
    )
    assert isinstance(blocks, list) and len(blocks) == 2
    assert original in blocks[0]


def test_author_uses_explicit_source_blocks_instead_of_parsing_untrusted_headings(monkeypatch):
    calls = []
    monkeypatch.setattr(
        scriptwriter,
        "rewrite_script_draft",
        lambda text, **kwargs: (
            calls.append(text)
            or '{"turns": [{"speaker": "mark", "text": "Новость."}, {"speaker": "nika", "text": "Уточнение."}]}'
        ),
    )
    block = "### 1. News\nТекст\n### 99. Это цитата внутри источника"
    scriptwriter.rewrite_chunked_dialogue_script_draft(block, chunk_size=1, source_blocks=[block])
    assert len(calls) == 1
    assert "### 99." in calls[0]


def test_grounded_scene_is_not_rewritten_just_to_fill_an_editor_stage(monkeypatch):
    from app.llm import scene_editor

    monkeypatch.setattr(
        scriptwriter,
        "rewrite_script_draft",
        lambda *a, **k: '{"turns": [{"speaker": "nika", "text": "Запуск не объявлен."}]}',
    )
    monkeypatch.setattr(
        scene_editor,
        "audit_scene",
        lambda *a, **k: {
            "supported_claims": [{"claim": "Запуск не объявлен."}],
            "unsupported_claims": [],
        },
    )

    def edit(*args, **kwargs):
        pytest.fail("A grounded scene must remain unchanged.")

    monkeypatch.setattr(scene_editor, "review_scene", edit)
    text, _ = scriptwriter.rewrite_chunked_dialogue_script_draft(
        "### 1. Source\nЗапуск не объявлен.", with_review=True
    )
    assert text == "nika: Запуск не объявлен."


def test_corrected_scene_must_pass_a_fresh_audit(monkeypatch):
    from app.llm import scene_editor

    events = []
    monkeypatch.setattr(
        scriptwriter,
        "rewrite_script_draft",
        lambda *a, **k: '{"turns": [{"speaker": "nika", "text": "Запуск завтра."}]}',
    )

    def audit(text, *args, **kwargs):
        events.append(("audit", text))
        return {
            "supported_claims": [],
            "unsupported_claims": [{"claim": "Запуск завтра.", "reason": "Срок не указан"}]
            if "завтра" in text
            else [],
        }

    def edit(*args, **kwargs):
        events.append(("edit", None))
        return {
            "script": "nika: Срок не указан.",
            "changes": ["Исправлена дата"],
            "unresolved_issues": [],
        }

    monkeypatch.setattr(scene_editor, "audit_scene", audit)
    monkeypatch.setattr(scene_editor, "review_scene", edit)
    text, _ = scriptwriter.rewrite_chunked_dialogue_script_draft(
        "### 1. Source\nСрок не указан.", with_review=True
    )
    assert text == "nika: Срок не указан."
    assert [event[0] for event in events] == ["audit", "edit", "audit"]
    assert events[-1][1] == text

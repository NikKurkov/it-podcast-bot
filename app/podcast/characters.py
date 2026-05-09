from dataclasses import dataclass


@dataclass(frozen=True)
class CharacterProfile:
    key: str
    name: str
    role: str
    short_description: str
    personality: str
    dialogue_function: list[str]
    speech_style: str
    catchphrases: list[str]
    default_tts_provider: str
    default_voice: str
    speaking_rate: str
    pause_after_ms: int


CHARACTER_PROFILES: dict[str, CharacterProfile] = {
    "mark": CharacterProfile(
        key="mark",
        name="Марк",
        role="Следователь / ведущий-аналитик",
        short_description=(
            "Ведёт выпуск как расследование, собирает факты, задаёт структуру "
            "и возвращает разговор к главной линии."
        ),
        personality="Спокойный, собранный, интригующий, с лёгким драматизмом.",
        dialogue_function=[
            "открывает выпуск",
            "формулирует главный вопрос",
            "восстанавливает цепочку событий",
            "иногда просит другого ведущего выбрать или добить тему",
            "подводит промежуточные итоги",
            "делает финальный вывод",
        ],
        speech_style="Спокойно, собранно, интригующе, с лёгким драматизмом.",
        catchphrases=[
            "Давайте восстановим цепочку событий.",
            "На первый взгляд это обычный релиз, но дальше начинается самое интересное.",
            "Вопрос не в том, что произошло. Вопрос — почему это стало возможным.",
        ],
        default_tts_provider="silero",
        default_voice="eugene",
        speaking_rate="normal",
        pause_after_ms=650,
    ),
    "gleb": CharacterProfile(
        key="gleb",
        name="Глеб",
        role="Старый Хакер",
        short_description=(
            "Опытный, циничный и саркастичный инженер. Помнит, что это уже было, "
            "видит слабые места и не верит в хайп."
        ),
        personality="Сухой юмор, инженерный скепсис, ворчит редко, но по делу.",
        dialogue_function=[
            "снижает градус хайпа",
            "сравнивает новости с прошлыми технологическими циклами",
            "показывает типичные инженерные ловушки",
            "может начать тему с ворчливого, но точного наблюдения",
            "добавляет сарказм и живость",
        ],
        speech_style="Сухой юмор, инженерный скепсис, иногда ворчит, но не токсичен.",
        catchphrases=[
            "Это не революция. Это старый паттерн, которому прикрутили красивый лендинг.",
            "Звучит отлично. Осталось понять, кто будет чинить это в три ночи.",
            "Я такое уже видел. Тогда оно называлось иначе и тоже падало.",
        ],
        default_tts_provider="silero",
        default_voice="aidar",
        speaking_rate="slightly_slow",
        pause_after_ms=750,
    ),
    "nika": CharacterProfile(
        key="nika",
        name="Ника",
        role="Деврел / объясняющая ведущая",
        short_description=(
            "Живая, остроумная и дружелюбная ведущая. Объясняет сложное человеческим "
            "языком и задаёт простые, но важные вопросы."
        ),
        personality="Энергичная, весёлая, с самоиронией, но без клоунады.",
        dialogue_function=[
            "задаёт простые вопросы без повторения одного шаблона",
            "помогает объяснять сложные вещи",
            "иногда перебивает, когда слышит важную практическую деталь",
            "делает переходы легче",
            "добавляет юмор",
            "проверяет практический смысл для обычного разработчика",
        ],
        speech_style="Энергично, весело, дружелюбно, с самоиронией.",
        catchphrases=[
            "То есть если перевести с инженерного на человеческий…",
            "Подождите, а мне завтра на работе это поможет или просто добавит ещё один YAML?",
            "Люблю новости, после которых надо обновлять не только зависимости, но и мировоззрение.",
        ],
        default_tts_provider="silero",
        default_voice="xenia",
        speaking_rate="slightly_fast",
        pause_after_ms=450,
    ),
    "artem": CharacterProfile(
        key="artem",
        name="Артём",
        role="Архитектор",
        short_description=(
            "Системный инженер. Видит архитектуру, инфраструктуру, безопасность, "
            "эксплуатацию, стоимость поддержки и последствия для production."
        ),
        personality="Спокойный, глубокий, точный, без лишней драмы.",
        dialogue_function=[
            "объясняет техническую механику",
            "говорит про архитектурные последствия",
            "отмечает риски безопасности и эксплуатации",
            "может первым вводить тему, если новость начинается с технического механизма",
            "переводит новость в практические выводы для команд",
        ],
        speech_style="Спокойно, глубоко, точно, без лекций на десять абзацев.",
        catchphrases=[
            "Главный вопрос не в том, можно ли это запустить. Главный вопрос — кто будет это поддерживать через полгода.",
            "Технически проблема не в самой модели, а в цепочке поставки вокруг неё.",
            "В продакшене это упирается в наблюдаемость, воспроизводимость и контроль доступа.",
        ],
        default_tts_provider="silero",
        default_voice="aidar",
        speaking_rate="slow",
        pause_after_ms=800,
    ),
}

_ALIASES = {
    "mark": "mark",
    "марк": "mark",
    "gleb": "gleb",
    "глеб": "gleb",
    "nika": "nika",
    "ника": "nika",
    "artem": "artem",
    "артем": "artem",
    "артём": "artem",
}


def resolve_character_key(value: str) -> str:
    normalized = value.strip().casefold().replace("ё", "е")
    if normalized in _ALIASES:
        return _ALIASES[normalized]

    supported = ", ".join(get_character_keys())
    raise ValueError(f"Unknown character: {value}. Supported characters: {supported}")


def get_character_profile(character_key: str) -> CharacterProfile:
    key = resolve_character_key(character_key)
    return CHARACTER_PROFILES[key]


def get_all_character_profiles() -> list[CharacterProfile]:
    return [CHARACTER_PROFILES[key] for key in get_character_keys()]


def get_character_keys() -> list[str]:
    return list(CHARACTER_PROFILES)


def format_character_profiles_for_prompt() -> str:
    blocks = []
    for profile in get_all_character_profiles():
        dialogue_lines = "\n".join(f"- {item}" for item in profile.dialogue_function)
        blocks.append(
            "\n".join(
                [
                    f"{profile.name} — {profile.role}.",
                    f"Ключ персонажа: {profile.key}",
                    f"Суть: {profile.short_description}",
                    f"Характер: {profile.personality}",
                    f"Стиль: {profile.speech_style}",
                    "Функция в диалоге:",
                    dialogue_lines,
                    (
                        "Важно: фирменные фразы персонажа хранятся только как "
                        "ориентир интонации. Не используй их дословно в сценарии."
                    ),
                    (
                        "Живой диалог: персонаж может обращаться к другим ведущим "
                        "по именам, перебивать коротким уточнением и реагировать "
                        "на предыдущую реплику, если это помогает теме."
                    ),
                ],
            ),
        )

    return "\n\n".join(blocks)

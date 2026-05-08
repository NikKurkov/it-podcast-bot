from datetime import datetime

from app.podcast.characters import format_character_profiles_for_prompt

_RU_MONTHS_GENITIVE = {
    1: "января",
    2: "февраля",
    3: "марта",
    4: "апреля",
    5: "мая",
    6: "июня",
    7: "июля",
    8: "августа",
    9: "сентября",
    10: "октября",
    11: "ноября",
    12: "декабря",
}


def build_scriptwriter_context() -> dict:
    return {
        "character_profiles": format_character_profiles_for_prompt(),
        "episode_date_ru": format_russian_episode_date(),
    }


def format_russian_episode_date(moment: datetime | None = None) -> str:
    moment = moment or datetime.now().astimezone()
    return f"{moment.day:02d} {_RU_MONTHS_GENITIVE[moment.month]}"

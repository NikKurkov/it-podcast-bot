from datetime import datetime

from app.config.settings import settings
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
_RU_ORDINAL_DAYS = {
    1: "первое",
    2: "второе",
    3: "третье",
    4: "четвёртое",
    5: "пятое",
    6: "шестое",
    7: "седьмое",
    8: "восьмое",
    9: "девятое",
    10: "десятое",
    11: "одиннадцатое",
    12: "двенадцатое",
    13: "тринадцатое",
    14: "четырнадцатое",
    15: "пятнадцатое",
    16: "шестнадцатое",
    17: "семнадцатое",
    18: "восемнадцатое",
    19: "девятнадцатое",
    20: "двадцатое",
    21: "двадцать первое",
    22: "двадцать второе",
    23: "двадцать третье",
    24: "двадцать четвёртое",
    25: "двадцать пятое",
    26: "двадцать шестое",
    27: "двадцать седьмое",
    28: "двадцать восьмое",
    29: "двадцать девятое",
    30: "тридцатое",
    31: "тридцать первое",
}


def build_scriptwriter_context() -> dict:
    return {
        "character_profiles": format_character_profiles_for_prompt(),
        "episode_date_ru": format_russian_episode_date(),
        "podcast_title": settings.podcast_title,
    }


def format_russian_episode_date(moment: datetime | None = None) -> str:
    moment = moment or datetime.now().astimezone()
    return f"{_RU_ORDINAL_DAYS[moment.day]} {_RU_MONTHS_GENITIVE[moment.month]}"

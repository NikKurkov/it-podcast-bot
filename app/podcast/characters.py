from dataclasses import dataclass


@dataclass(frozen=True)
class CharacterProfile:
    key: str
    name: str
    gender: str
    role: str
    speech_style: str
    default_voice: str
    pause_after_ms: int


CHARACTER_PROFILES: dict[str, CharacterProfile] = {
    "mark": CharacterProfile(
        key="mark",
        name="Марк",
        gender="мужской",
        role="Любопытный ведущий и собеседник",
        speech_style="Любопытен к новому, быстро замечает необычную деталь и задаёт содержательный вопрос. Разговорно и ясно связывает мысли, умеет уступить инициативу и изменить мнение.",
        default_voice="eugene",
        pause_after_ms=650,
    ),
    "gleb": CharacterProfile(
        key="gleb",
        name="Глеб",
        gender="мужской",
        role="Опытный инженер с сухим юмором",
        speech_style="Смотрит на доказательства и последствия для эксплуатации. Любит простые работающие решения, способен увлечься хорошей идеей и признать чужую правоту. Сухой, доброжелательный юмор.",
        default_voice="aidar",
        pause_after_ms=750,
    ),
    "nika": CharacterProfile(
        key="nika",
        name="Ника",
        gender="женский",
        role="Практичный разработчик и внимательная собеседница",
        speech_style="Тёплая, остроумная и компетентная. Замечает, как решение повлияет на работу и привычки людей. Задаёт точные вопросы, сама объясняет детали и подхватывает удачную шутку.",
        default_voice="xenia",
        pause_after_ms=450,
    ),
    "artem": CharacterProfile(
        key="artem",
        name="Артём",
        gender="мужской",
        role="Инженер, объясняющий устройство систем",
        speech_style="Спокойный и конкретный. Задумывается над устройством системы и подхватывает вопрос собеседника. Раскрывает причинную связь или уместный условный пример, умеет кратко возразить.",
        default_voice="aidar",
        pause_after_ms=800,
    ),
}

_ALIASES = {
    value.casefold().replace("ё", "е"): profile.key
    for profile in CHARACTER_PROFILES.values()
    for value in (profile.key, profile.name)
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


def get_active_character_keys() -> list[str]:
    from app.config.settings import settings

    if settings.podcast_participants is None:
        return get_character_keys()
    keys = [
        resolve_character_key(value)
        for value in settings.podcast_participants.split(",")
        if value.strip()
    ]
    if not keys:
        raise ValueError("Configure at least one known podcast participant.")
    return list(dict.fromkeys(keys))


def format_character_profiles_for_prompt() -> str:
    return "\n".join(
        f"{profile.key}: {profile.name}; род: {profile.gender}; {profile.role}; {profile.speech_style}"
        for profile in (CHARACTER_PROFILES[key] for key in get_active_character_keys())
    )

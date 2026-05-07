from app.podcast.characters import format_character_profiles_for_prompt


def build_scriptwriter_context() -> dict:
    return {
        "character_profiles": format_character_profiles_for_prompt(),
    }

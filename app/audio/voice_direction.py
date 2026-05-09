import re

from app.audio.models import DialogueLine

_TRANSITION_RE = re.compile(
    r"(следующ|дальше|теперь|а\s+вот|что\s+у\s+нас\s+дальше|переходим|перейд[её]м)",
    re.IGNORECASE,
)
_RUNDOWN_RE = re.compile(
    r"(сегодня\s+в\s+выпуске|в\s+выпуске|коротко\s+по\s+темам)",
    re.IGNORECASE,
)
_HUMAN_ASIDE_RE = re.compile(
    r"("
    r"кхм|кашл|клаца|клавиатур|микрофон|отвернул|будь\s+здоров|"
    r"шорох|шурш|птиц|собак|фонит|стол|здоров"
    r")",
    re.IGNORECASE,
)
_INTERRUPTION_RE = re.compile(
    r"(подожди|секунду|ой,\s*да\s+ладно|стоп|погоди|можно\s+я)",
    re.IGNORECASE,
)
_VERDICT_RE = re.compile(
    r"(финальн|вывод|проверьте|зафиксируйте|заложите|отключите|вынесите)",
    re.IGNORECASE,
)


def apply_voice_direction(
    speaker: str,
    text: str,
    *,
    base_pause_after_ms: int,
) -> DialogueLine:
    emotion = _detect_emotion(text)
    pause_after_ms = _pause_for_emotion(emotion, base_pause_after_ms)
    return DialogueLine(
        speaker=speaker,
        text=text,
        emotion=emotion,
        pause_after_ms=pause_after_ms,
    )


def _detect_emotion(text: str) -> str | None:
    if _RUNDOWN_RE.search(text):
        return "rundown"
    if _HUMAN_ASIDE_RE.search(text):
        return "aside"
    if _INTERRUPTION_RE.search(text):
        return "interruption"
    if _TRANSITION_RE.search(text):
        return "transition"
    if _VERDICT_RE.search(text):
        return "verdict"
    return None


def _pause_for_emotion(emotion: str | None, base_pause_after_ms: int) -> int:
    if emotion == "rundown":
        return max(base_pause_after_ms, 760)
    if emotion == "transition":
        return max(base_pause_after_ms, 820)
    if emotion == "aside":
        return min(base_pause_after_ms, 380)
    if emotion == "interruption":
        return min(base_pause_after_ms, 340)
    if emotion == "verdict":
        return max(base_pause_after_ms, 700)
    return base_pause_after_ms

"""Render Russian numerals before the speech provider can discard their digits."""

import re
from datetime import date

from num2words import num2words

_MONTHS = (
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)
_DATE_CASES = {"к": "d", "с": "g", "со": "g", "до": "g", "от": "g", "после": "g", "около": "g"}
_DATE_PREPOSITION = rf"(?:(?P<prep>{'|'.join(_DATE_CASES)})\s+)?"
_DATE = re.compile(
    rf"\b{_DATE_PREPOSITION}(?P<day>0?[1-9]|[12]\d|3[01])\s+"
    rf"(?P<month>{'|'.join(_MONTHS)})\b",
    re.IGNORECASE,
)
_NUMERIC_DATE = re.compile(
    rf"\b{_DATE_PREPOSITION}(?P<calendar>\d{{1,2}}\.\d{{1,2}}\.\d{{4}}"
    rf"|\d{{4}}-\d{{2}}-\d{{2}})(?!\w|\.\d)",
    re.IGNORECASE,
)
_US_DOLLARS = re.compile(r"(\$\s*-?)(\d{1,3}(?:,\d{3})+)(?![\d,])")
_YEAR = re.compile(
    r"\b(\d{4})(?=\s+(?:[а-яё]+\s+)?(года|году|годом|год)\b)", re.IGNORECASE
)
_ARTICLE = re.compile(r"\b(в статье)\s+(\d{1,6})\b", re.IGNORECASE)
_VERSION = re.compile(
    r"(?<!\w)(?:(?P<prefix>v)(?P<with_prefix>\d+(?:\.\d+)*)"
    r"|(?P<bare>\d+(?:\.\d+){2,})"
    r"|(?P<label>верси(?:я|ю|и|ей)|релиз(?:а|е)?|[a-z][a-z0-9]+|пайтон|линукс)"
    r"(?P<spacer>\s+)(?P<labelled>\d+(?:\.\d+)+))(?!\.\d|\w)",
    re.IGNORECASE,
)
_NUMBER = re.compile(
    r"(?P<currency_prefix>[$€₽]\s*)?(?P<sign>(?<!\w)[−-])?"
    r"(?P<number>\d+(?:[ \u00a0\u202f]\d{3}(?!\d))*(?:[.,]\d+)?)"
    r"(?P<percent>\s*%)?(?P<scale>\s+(?:тыс|млн|млрд|трлн)\b\.?)?"
    r"(?P<currency_suffix>\s*[$€₽]|\s+руб\b\.?)?",
    re.IGNORECASE,
)
_SCALES = {
    "тыс": ("тысяча", "тысячи", "тысяч", "тысячи"),
    "млн": ("миллион", "миллиона", "миллионов", "миллиона"),
    "млрд": ("миллиард", "миллиарда", "миллиардов", "миллиарда"),
    "трлн": ("триллион", "триллиона", "триллионов", "триллиона"),
}
_CURRENCIES = {
    "$": ("доллар", "доллара", "долларов", "доллара"),
    "€": ("евро", "евро", "евро", "евро"),
    "₽": ("рубль", "рубля", "рублей", "рубля"),
}
_PERCENT = ("процент", "процента", "процентов", "процента")


def normalize_spoken_dates(text: str) -> str:
    def day(match: re.Match) -> str:
        prep = match["prep"]
        ordinal = _day(int(match["day"]), prep)
        return " ".join(part for part in (prep, ordinal, match["month"]) if part)

    return _DATE.sub(day, text)


def normalize_spoken_versions(text: str) -> str:
    """Expand versions and numeric calendar dates before name detection."""
    def calendar_date(match: re.Match) -> str:
        raw = match["calendar"]
        try:
            if "." in raw:
                day, month, year = map(int, raw.split("."))
                value = date(year, month, day)
            else:
                value = date.fromisoformat(raw)
        except ValueError:
            return match[0]
        if not 1900 <= value.year <= 2199:
            return match[0]
        prep = match["prep"]
        year_words = _words(value.year, to="ordinal", case="g")
        return " ".join(
            part for part in (
                prep, _day(value.day, prep), _MONTHS[value.month - 1], year_words, "года"
            ) if part
        )

    def version(match: re.Match) -> str:
        components = (match["with_prefix"] or match["bare"] or match["labelled"]).split(".")
        spoken = " точка ".join(_cardinal(component) for component in components)
        if match["label"]:
            return match["label"] + match["spacer"] + spoken
        return f"ви {spoken}" if match["prefix"] else spoken

    return _VERSION.sub(version, _NUMERIC_DATE.sub(calendar_date, text))


def normalize_spoken_numbers(text: str) -> str:
    text = normalize_spoken_dates(text)
    text = _YEAR.sub(
        lambda match: _words(
            int(match[1]), to="ordinal",
            case={"года": "g", "году": "p", "годом": "i", "год": "n"}[match[2].lower()],
        ),
        text,
    )
    text = _ARTICLE.sub(
        lambda match: f"{match[1]} {_words(int(match[2]), to='ordinal', gender='f', case='p')}",
        text,
    )

    text = normalize_spoken_versions(text)
    text = _US_DOLLARS.sub(lambda match: match[1] + match[2].replace(",", " "), text)

    def number(match: re.Match) -> str:
        value = re.sub(r"\s", "", match["number"]).replace(",", ".")
        prefix = text[:match.start()]
        suffix = text[match.end():]
        genitive = bool(re.search(r"\b(?:до|от|около|более|менее|свыше|из|без)\s+$", prefix, re.I))
        scale = (match["scale"] or "").strip().rstrip(".").lower()
        feminine = scale == "тыс" or bool(re.match(r"\s+тысяч\w*\b", suffix, re.I))
        spoken = _cardinal(value, case="g" if genitive else "n", gender="f" if feminine else "m")
        if match["sign"]:
            spoken = "минус " + spoken
        if match["percent"]:
            spoken += " " + _noun(value, _PERCENT, genitive)
        currency = match["currency_prefix"] or match["currency_suffix"]
        if scale:
            spoken += " " + _noun(value, _SCALES[scale], genitive)
        if currency:
            symbol = currency.strip().lower().rstrip(".")
            forms = _CURRENCIES["₽" if symbol == "руб" else symbol]
            spoken += " " + (forms[2] if scale else _noun(value, forms, genitive))
        abbreviation = match["currency_suffix"] or match["scale"] or ""
        if abbreviation.endswith(".") and (not suffix or re.match(r"\s+[А-ЯЁ]", suffix)):
            spoken += "."
        before = " " if prefix and prefix[-1].isalpha() else ""
        after = " " if suffix and suffix[0].isalpha() else ""
        return before + spoken + after

    return _NUMBER.sub(number, text)


def _day(value: int, prep: str | None) -> str:
    case = _DATE_CASES[prep.lower()] if prep else "n"
    return _words(value, to="ordinal", gender="n", case=case)


def _words(value: int | str, **kwargs: str) -> str:
    return num2words(value, lang="ru", **kwargs)


def _cardinal(value: str, **kwargs: str) -> str:
    whole, _, fraction = value.partition(".")
    if len(whole) > 15 or len(fraction) > 8 or (len(whole) > 1 and whole.startswith("0")):
        return " ".join("точка" if char == "." else _words(int(char)) for char in value)
    return _words(value, **kwargs)


def _noun(value: str, forms: tuple[str, str, str, str], genitive: bool) -> str:
    if "." in value:
        return forms[3]
    last_two_digits = int(value[-2:])
    if last_two_digits % 10 == 1 and last_two_digits != 11:
        return forms[1 if genitive else 0]
    if not genitive and last_two_digits % 10 in (2, 3, 4) and last_two_digits not in (12, 13, 14):
        return forms[1]
    return forms[2]

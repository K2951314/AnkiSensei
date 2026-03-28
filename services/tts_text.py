from __future__ import annotations

import re

ALNUM_CODE_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])([A-Za-z]+)(\d+)([A-Za-z]+)?(?![A-Za-z0-9])"
)
COMPOUND_UNIT_PATTERN = re.compile(
    r"(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>mm|cm|m)\s*/\s*(?P<per>rev|min)\b",
    re.IGNORECASE,
)
SINGLE_UNIT_PATTERN = re.compile(
    r"(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>rpm|mm|cm|m|%)(?:\b|$)",
    re.IGNORECASE,
)
NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?")

FULLWIDTH_TRANSLATION = str.maketrans(
    {
        "０": "0",
        "１": "1",
        "２": "2",
        "３": "3",
        "４": "4",
        "５": "5",
        "６": "6",
        "７": "7",
        "８": "8",
        "９": "9",
        "％": "%",
        "．": ".",
        "／": "/",
        "－": "-",
    }
)

DIGIT_READINGS = {
    "0": "ぜろ",
    "1": "いち",
    "2": "に",
    "3": "さん",
    "4": "よん",
    "5": "ご",
    "6": "ろく",
    "7": "なな",
    "8": "はち",
    "9": "きゅう",
}
INT_READINGS = {
    "ones": {
        1: "いち",
        2: "に",
        3: "さん",
        4: "よん",
        5: "ご",
        6: "ろく",
        7: "なな",
        8: "はち",
        9: "きゅう",
    },
    "tens": {
        1: "じゅう",
        2: "にじゅう",
        3: "さんじゅう",
        4: "よんじゅう",
        5: "ごじゅう",
        6: "ろくじゅう",
        7: "ななじゅう",
        8: "はちじゅう",
        9: "きゅうじゅう",
    },
    "hundreds": {
        1: "ひゃく",
        2: "にひゃく",
        3: "さんびゃく",
        4: "よんひゃく",
        5: "ごひゃく",
        6: "ろっぴゃく",
        7: "ななひゃく",
        8: "はっぴゃく",
        9: "きゅうひゃく",
    },
    "thousands": {
        1: "せん",
        2: "にせん",
        3: "さんぜん",
        4: "よんせん",
        5: "ごせん",
        6: "ろくせん",
        7: "ななせん",
        8: "はっせん",
        9: "きゅうせん",
    },
}
UNIT_READINGS = {
    "%": "パーセント",
    "mm": "ミリメートル",
    "cm": "センチメートル",
    "m": "メートル",
    "rpm": "アールピーエム",
    "rev": "レブ",
    "min": "分",
}
DECIMAL_POINT_READING = "てん"
ZERO_READING = "れい"


def normalize_tts_text(text: str) -> str:
    normalized = text.translate(FULLWIDTH_TRANSLATION)
    normalized = COMPOUND_UNIT_PATTERN.sub(_replace_compound_unit, normalized)
    normalized = SINGLE_UNIT_PATTERN.sub(_replace_single_unit, normalized)
    normalized = ALNUM_CODE_PATTERN.sub(_replace_alnum_code, normalized)
    normalized = NUMBER_PATTERN.sub(_replace_number, normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    normalized = re.sub(r"\s+([。、\.,\?\!？！])", r"\1", normalized)
    return normalized


def _replace_compound_unit(match: re.Match[str]) -> str:
    number_text = match.group("num")
    unit = match.group("unit").lower()
    per = match.group("per").lower()
    number_reading = _read_number(number_text)
    unit_reading = UNIT_READINGS.get(unit, unit)
    per_reading = UNIT_READINGS.get(per, per)
    return _wrap_reading(f"{number_reading} {unit_reading}毎{per_reading}")


def _replace_single_unit(match: re.Match[str]) -> str:
    number_text = match.group("num")
    unit = match.group("unit").lower()
    number_reading = _read_number(number_text)
    unit_reading = UNIT_READINGS.get(unit, unit)
    return _wrap_reading(f"{number_reading} {unit_reading}")


def _replace_alnum_code(match: re.Match[str]) -> str:
    prefix = match.group(1) or ""
    number_text = match.group(2) or ""
    suffix = match.group(3) or ""
    number_reading = _read_int(number_text)
    parts = [prefix, number_reading]
    if suffix:
        parts.append(suffix)
    return _wrap_reading(" ".join(part for part in parts if part))


def _replace_number(match: re.Match[str]) -> str:
    return _wrap_reading(_read_number(match.group(0)))


def _read_number(number_text: str) -> str:
    if "." in number_text:
        return _read_decimal(number_text)
    return _read_int(number_text)


def _read_decimal(number_text: str) -> str:
    integer_text, fractional_text = number_text.split(".", 1)
    integer_reading = _read_int(integer_text or "0")
    fractional_reading = " ".join(DIGIT_READINGS.get(ch, ch) for ch in fractional_text)
    return f"{integer_reading}{DECIMAL_POINT_READING} {fractional_reading}".strip()


def _read_int(number_text: str) -> str:
    if not number_text:
        return ZERO_READING
    try:
        value = int(number_text)
    except ValueError:
        return _read_digits(number_text)

    if value == 0:
        return ZERO_READING
    if value > 9999:
        return _read_digits(number_text)

    parts: list[str] = []
    thousands = value // 1000
    hundreds = (value % 1000) // 100
    tens = (value % 100) // 10
    ones = value % 10

    if thousands:
        parts.append(INT_READINGS["thousands"][thousands])
    if hundreds:
        parts.append(INT_READINGS["hundreds"][hundreds])
    if tens:
        parts.append(INT_READINGS["tens"][tens])
    if ones:
        parts.append(INT_READINGS["ones"][ones])
    return "".join(parts)


def _read_digits(number_text: str) -> str:
    return " ".join(DIGIT_READINGS.get(ch, ch) for ch in number_text)


def _wrap_reading(reading: str) -> str:
    return f" {reading} "

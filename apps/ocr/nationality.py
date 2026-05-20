"""Shared nationality extraction from OCR text and Azure field values."""

from __future__ import annotations

import re
from typing import Any

from documents.ocr_parser import normalize_space

# Country / ISO tokens → labels aligned with deal form NATIONALITIES + QIC resolution.
# Use country names where the CRM dropdown lists them (e.g. Pakistan, Yemen).
# QIC quote lookup maps those names to insurer codes in qic_masterdata.py.
COUNTRY_NAME_ALIASES: dict[str, str] = {
    "INDIA": "Indian",
    "UNITED ARAB EMIRATES": "UAE",
    "U.A.E.": "UAE",
    "YEMENI": "Yemen",
}

NATIONALITY_CODE_ALIASES: dict[str, str] = {
    "IND": "Indian",
    "PAK": "Pakistan",
    "BGD": "Bangladesh",
    "PHL": "Philippines",
    "EGY": "Egypt",
    "JOR": "Jordan",
    "LBN": "Lebanon",
    "SYR": "Syria",
    "YEM": "Yemen",
    "ARE": "UAE",
    "UAE": "UAE",
    "GBR": "United Kingdom",
    "USA": "United States",
}

ARABIC_NATIONALITY_NAMES: dict[str, str] = {
    "الهند": "Indian",
    "هندي": "Indian",
    "هندية": "Indian",
    "باكستان": "Pakistan",
    "باكستاني": "Pakistan",
    "باكستانية": "Pakistan",
    "مصر": "Egypt",
    "مصري": "Egypt",
    "مصرية": "Egypt",
    "الفلبين": "Philippines",
    "فلبيني": "Philippines",
    "فلبينية": "Philippines",
    "بنغلاديش": "Bangladesh",
    "سوريا": "Syria",
    "الأردن": "Jordan",
    "لبنان": "Lebanon",
    "المملكة المتحدة": "United Kingdom",
    "الولايات المتحدة": "United States",
    "الإمارات": "UAE",
    "الامارات": "UAE",
    "إماراتي": "UAE",
    "اماراتي": "UAE",
}

ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
LATIN_RE = re.compile(r"[A-Za-z]")
NATIONALITY_LABEL_RE = re.compile(
    r"^(?:Nationality|الجنسية)\s*[:.\-]?\s*(.*)$",
    re.IGNORECASE,
)
NATIONALITY_EMBEDDED_RE = re.compile(
    r"^(?:Nationality|الجنسية)\s*[:.\-]?\s*(.+)$",
    re.IGNORECASE,
)
LATIN_NATIONALITY_INLINE_RE = re.compile(
    r"\bNationality\s*[:.\-]\s*([A-Za-z][A-Za-z .\-]{1,40})",
    re.IGNORECASE,
)
ISO_CODE_RE = re.compile(r"^[A-Z]{2,3}$")


def _lines(text: str) -> list[str]:
    return [normalize_space(line) for line in text.splitlines() if normalize_space(line)]


def strip_nationality_label(value: str) -> str:
    cleaned = normalize_space(value)
    if not cleaned:
        return ""

    match = NATIONALITY_EMBEDDED_RE.match(cleaned)
    if match:
        return normalize_space(match.group(1)).strip(" .,:;")

    return cleaned.strip(" .,:;")


def is_mostly_arabic(value: str) -> bool:
    letters = [char for char in value if char.isalpha()]
    if not letters:
        return False
    arabic_count = len(ARABIC_RE.findall(value))
    return arabic_count / len(letters) >= 0.6


def has_latin_letters(value: str) -> bool:
    return bool(LATIN_RE.search(value))


def latin_ratio(value: str) -> float:
    letters = [char for char in value if char.isalpha()]
    if not letters:
        return 0.0
    latin_count = len(LATIN_RE.findall(value))
    return latin_count / len(letters)


def translate_arabic_nationality(value: str) -> str:
    cleaned = normalize_space(value)
    if cleaned in ARABIC_NATIONALITY_NAMES:
        return ARABIC_NATIONALITY_NAMES[cleaned]

    for arabic, english in ARABIC_NATIONALITY_NAMES.items():
        if arabic in cleaned:
            return english

    return ""


def _collect_string_candidates(value: Any) -> list[str]:
    candidates: list[str] = []

    def add(candidate: Any) -> None:
        if isinstance(candidate, str):
            stripped = strip_nationality_label(candidate)
            if stripped:
                candidates.append(stripped)

    if isinstance(value, str):
        add(value)
        return candidates

    if isinstance(value, dict):
        for key in ("code", "name", "content", "value", "country"):
            add(value.get(key))
        return candidates

    for attr in ("code", "name", "content", "value"):
        add(getattr(value, attr, None))

    return candidates


def pick_english_nationality(candidates: list[str]) -> str:
    if not candidates:
        return ""

    for candidate in candidates:
        token = candidate.strip().upper()
        if ISO_CODE_RE.fullmatch(token):
            return candidate.strip()

    for candidate in candidates:
        if has_latin_letters(candidate) and latin_ratio(candidate) >= 0.7:
            return candidate.strip()

    for candidate in candidates:
        if is_mostly_arabic(candidate):
            translated = translate_arabic_nationality(candidate)
            if translated:
                return translated

    for candidate in candidates:
        if has_latin_letters(candidate):
            return candidate.strip()

    return ""


def _coerce_nationality_value(value: Any) -> str:
    return pick_english_nationality(_collect_string_candidates(value))


def normalize_nationality(value: str) -> str:
    cleaned = strip_nationality_label(value)
    if not cleaned:
        return ""

    if is_mostly_arabic(cleaned):
        translated = translate_arabic_nationality(cleaned)
        if translated:
            return translated

    upper = cleaned.upper()
    if ISO_CODE_RE.fullmatch(upper) and upper in NATIONALITY_CODE_ALIASES:
        return NATIONALITY_CODE_ALIASES[upper]

    if upper in NATIONALITY_CODE_ALIASES:
        return NATIONALITY_CODE_ALIASES[upper]

    if upper in COUNTRY_NAME_ALIASES:
        return COUNTRY_NAME_ALIASES[upper]

    return cleaned


def _nationality_from_nationality_label(lines: list[str]) -> str:
    for index, line in enumerate(lines):
        match = NATIONALITY_LABEL_RE.match(line)
        if not match:
            continue

        inline = strip_nationality_label(match.group(1))
        if inline and not is_mostly_arabic(inline):
            return inline

        following = pick_english_nationality(
            [normalize_space(item) for item in lines[index + 1 : index + 5]]
        )
        if following:
            return following

    latin_match = LATIN_NATIONALITY_INLINE_RE.search("\n".join(lines))
    if latin_match:
        return normalize_space(latin_match.group(1))

    return ""


def extract_nationality_from_ocr(
    text: str,
    *,
    existing_fields: dict[str, Any] | None = None,
) -> str:
    """Extract English nationality from Nationality / الجنسية label or Azure fields."""
    existing_fields = existing_fields or {}

    for key in ("Nationality", "nationality"):
        if key not in existing_fields:
            continue
        coerced = _coerce_nationality_value(existing_fields[key])
        if coerced:
            return normalize_nationality(coerced)

    labeled = _nationality_from_nationality_label(_lines(text))
    if labeled:
        return normalize_nationality(labeled)

    return ""


# Backward-compatible alias used by feature parsers (e.g. deals mulkiya).
extract_nationality_from_emirates_id = extract_nationality_from_ocr

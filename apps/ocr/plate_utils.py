"""Shared plate-source / emirate normalization for OCR field mapping."""

from __future__ import annotations

import re

from documents.ocr_parser import normalize_space

ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
ARABIC_DIACRITICS_RE = re.compile(
    r"[\u0640\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]"
)

ARABIC_EMIRATE_NAMES: dict[str, str] = {
    "دبي": "DUBAI",
    "دبى": "DUBAI",
    "إمارة دبي": "DUBAI",
    "امارة دبي": "DUBAI",
    "أبو ظبي": "ABU DHABI",
    "ابو ظبي": "ABU DHABI",
    "أبوظبي": "ABU DHABI",
    "ابوظبي": "ABU DHABI",
    "إمارة أبوظبي": "ABU DHABI",
    "امارة ابوظبي": "ABU DHABI",
    "الشارقة": "SHARJAH",
    "الشارقه": "SHARJAH",
    "شارقة": "SHARJAH",
    "إمارة الشارقة": "SHARJAH",
    "عجمان": "AJMAN",
    "إمارة عجمان": "AJMAN",
    "أم القيوين": "UMM AL QUWAIN",
    "ام القيوين": "UMM AL QUWAIN",
    "ام القيوين": "UMM AL QUWAIN",
    "الفجيرة": "FUJAIRAH",
    "الفجيره": "FUJAIRAH",
    "فجيرة": "FUJAIRAH",
    "رأس الخيمة": "RAS AL KHAIMAH",
    "راس الخيمة": "RAS AL KHAIMAH",
    "رأس الخيمه": "RAS AL KHAIMAH",
    "راس الخيمه": "RAS AL KHAIMAH",
    "العين": "AL AIN",
    "مدينة العين": "AL AIN",
}

EMIRATE_ALIASES: dict[str, str] = {
    "DUBAI": "DUBAI",
    "ABU DHABI": "ABU DHABI",
    "ABUDHABI": "ABU DHABI",
    "AL AIN": "AL AIN",
    "SHARJAH": "SHARJAH",
    "AJMAN": "AJMAN",
    "UMM AL QUWAIN": "UMM AL QUWAIN",
    "UMM AL QUWIN": "UMM AL QUWAIN",
    "FUJAIRAH": "FUJAIRAH",
    "RAS AL KHAIMAH": "RAS AL KHAIMAH",
    "RAK": "RAS AL KHAIMAH",
}

PLACE_OF_ISSUE_EMBEDDED_RE = re.compile(
    r"^(?:Place\s*of\s*Issue|Licensing\s*Authority)\s*[:.\-]?\s*(.+)$",
    re.IGNORECASE,
)


def _detect_emirate(text: str) -> str | None:
    """Detect UAE emirate name from free text."""
    upper = text.upper()
    for alias, canonical in EMIRATE_ALIASES.items():
        if alias in upper:
            return canonical
    return None


def is_mostly_arabic(value: str) -> bool:
    """Return True when the string is primarily Arabic script."""
    letters = [char for char in value if char.isalpha()]
    if not letters:
        return False
    arabic_count = len(ARABIC_RE.findall(value))
    return arabic_count / len(letters) >= 0.6


def _normalize_arabic_key(value: str) -> str:
    """Normalize Arabic OCR text for dictionary lookup."""
    text = ARABIC_DIACRITICS_RE.sub("", value)
    text = (
        text.replace("أ", "ا")
        .replace("إ", "ا")
        .replace("آ", "ا")
        .replace("ى", "ي")
        .replace("ة", "ه")
    )
    return normalize_space(text)


def translate_arabic_emirate(value: str) -> str:
    """Map Arabic place-of-issue text to an English emirate label."""
    cleaned = normalize_space(value)
    if not cleaned:
        return ""

    candidates = {cleaned, _normalize_arabic_key(cleaned)}
    for candidate in candidates:
        if candidate in ARABIC_EMIRATE_NAMES:
            return ARABIC_EMIRATE_NAMES[candidate]

    for arabic, english in sorted(
        ARABIC_EMIRATE_NAMES.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        for candidate in candidates:
            if arabic in candidate:
                return english

    return ""


def strip_place_of_issue_label(value: str) -> str:
    """Remove duplicated Place of Issue label text from OCR/Azure values."""
    cleaned = normalize_space(value)
    if not cleaned:
        return ""

    match = PLACE_OF_ISSUE_EMBEDDED_RE.match(cleaned)
    if match:
        return normalize_space(match.group(1)).strip(" .,:;")

    return cleaned.strip(" .,:;")


def normalize_plate_source(value: str) -> str:
    """Normalize place of issue text to a CRM plate source label."""
    cleaned = strip_place_of_issue_label(value)
    if not cleaned:
        return ""

    if is_mostly_arabic(cleaned) or ARABIC_RE.search(cleaned):
        return translate_arabic_emirate(cleaned)

    detected = _detect_emirate(cleaned)
    if detected:
        return detected

    if cleaned.isascii():
        return cleaned.upper()

    return ""

"""Parse UAE Emirates ID OCR text for fields missing from Azure structured output."""

from __future__ import annotations

import re
from typing import Any

from documents.ocr_parser import normalize_space

from apps.ocr.plate_utils import _detect_emirate

# Map short Latin codes printed on Emirates ID cards.
# English country names that should match CRM nationality dropdown labels.
COUNTRY_NAME_ALIASES: dict[str, str] = {
    "INDIA": "Indian",
    "UNITED ARAB EMIRATES": "UAE",
    "U.A.E.": "UAE",
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
    "ARE": "UAE",
    "UAE": "UAE",
    "GBR": "United Kingdom",
    "USA": "United States",
}

# Common Arabic nationality labels on UAE Emirates ID cards.
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

EMIRATES_ID_DIGITS_RE = re.compile(r"784[-\s]?\d{4}[-\s]?\d{7}[-\s]?\d")

EMIRATES_ID_FIELD_KEYS: tuple[str, ...] = (
    "DocumentNumber",
    "emirates_id",
    "id_number",
    "IDNumber",
    "identity_number",
)

ID_NUMBER_LABELS: tuple[str, ...] = (
    "id number",
    "id no",
    "identity number",
    "رقم الهوية",
)

ID_NUMBER_EMBEDDED_RE = re.compile(
    r"^(?:ID|Identity)\s*Number\s*[:.\-]?\s*(.+)$",
    re.IGNORECASE,
)
ID_NUMBER_LINE_RE = re.compile(r"^ID\s*Number\.?$", re.IGNORECASE)
ID_NUMBER_INLINE_RE = re.compile(
    r"\b(?:ID|Identity)\s*Number\s*[:.\-]?\s*(784[-\s]?\d{4}[-\s]?\d{7}[-\s]?\d)",
    re.IGNORECASE,
)

SEX_FIELD_KEYS: tuple[str, ...] = (
    "Sex",
    "sex",
    "gender",
    "Gender",
)

SEX_EMBEDDED_RE = re.compile(r"^Sex\b\s*[:.\-]?\s*(.+)$", re.IGNORECASE)
SEX_LINE_RE = re.compile(r"^Sex\b", re.IGNORECASE)
SEX_VALUE_RE = re.compile(r"^[MF]\.?$", re.IGNORECASE)
SEX_INLINE_RE = re.compile(r"\bSex\b\s*[:.\-]?\s*([MF])\b", re.IGNORECASE)

# CRM dropdown labels (promise-client EMIRATES constant).
CRM_EMIRATE_LABELS: dict[str, str] = {
    "SHARJAH": "SHARJAH.  U.A.E",
    "RAS AL KHAIMAH": "RAS AL-KHAIMAH",
    "UMM AL QUWAIN": "UMM AL-QUWAIN",
}

ISSUING_PLACE_FIELD_KEYS: tuple[str, ...] = (
    "IssuingPlace",
    "issuing_place",
    "PlaceOfIssue",
    "place_of_issue",
)

ISSUING_PLACE_EMBEDDED_RE = re.compile(
    r"^(?:Issuing\s*Place|Issueing\s*Place|Place\s*of\s*Issue)\s*[:.\-]?\s*(.+)$",
    re.IGNORECASE,
)
ISSUING_PLACE_LABEL_RE = re.compile(
    r"^(?:Issuing\s*Place|Issueing\s*Place|Place\s*of\s*Issue)\s*[:.\-]?\s*(.*)$",
    re.IGNORECASE,
)


def _lines(text: str) -> list[str]:
    """Return normalized non-empty lines from OCR text."""
    return [normalize_space(line) for line in text.splitlines() if normalize_space(line)]


def strip_nationality_label(value: str) -> str:
    """Remove duplicated ``Nationality`` label text from OCR/Azure values."""
    cleaned = normalize_space(value)
    if not cleaned:
        return ""

    match = NATIONALITY_EMBEDDED_RE.match(cleaned)
    if match:
        return normalize_space(match.group(1)).strip(" .,:;")

    return cleaned.strip(" .,:;")


def is_mostly_arabic(value: str) -> bool:
    """Return True when the string is primarily Arabic script."""
    letters = [char for char in value if char.isalpha()]
    if not letters:
        return False
    arabic_count = len(ARABIC_RE.findall(value))
    return arabic_count / len(letters) >= 0.6


def has_latin_letters(value: str) -> bool:
    """Return True when the string contains Latin letters."""
    return bool(LATIN_RE.search(value))


def latin_ratio(value: str) -> float:
    """Return the share of Latin letters among all letters."""
    letters = [char for char in value if char.isalpha()]
    if not letters:
        return 0.0
    latin_count = len(LATIN_RE.findall(value))
    return latin_count / len(letters)


def translate_arabic_nationality(value: str) -> str:
    """Map Arabic nationality text to an English label when known."""
    cleaned = normalize_space(value)
    if cleaned in ARABIC_NATIONALITY_NAMES:
        return ARABIC_NATIONALITY_NAMES[cleaned]

    for arabic, english in ARABIC_NATIONALITY_NAMES.items():
        if arabic in cleaned:
            return english

    return ""


def _collect_string_candidates(value: Any) -> list[str]:
    """Gather string candidates from an Azure nationality value."""
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
    """Choose the best English nationality from OCR/Azure candidates."""
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
    """Convert Azure Nationality field values to an English string."""
    return pick_english_nationality(_collect_string_candidates(value))


def normalize_nationality(value: str) -> str:
    """Normalize nationality codes and Arabic labels to English display values."""
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
    """Read the English value for the Nationality / الجنسية label."""
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


def strip_issuing_place_label(value: str) -> str:
    """Remove duplicated Issuing Place label text from OCR/Azure values."""
    cleaned = normalize_space(value)
    if not cleaned:
        return ""

    match = ISSUING_PLACE_EMBEDDED_RE.match(cleaned)
    if match:
        return normalize_space(match.group(1)).strip(" .,:;")

    return cleaned.strip(" .,:;")


def normalize_emirate(value: str) -> str:
    """Normalize issuing place text to a CRM emirate dropdown label."""
    cleaned = strip_issuing_place_label(value)
    if not cleaned:
        return ""

    detected = _detect_emirate(cleaned)
    if detected:
        return CRM_EMIRATE_LABELS.get(detected, detected)

    upper = cleaned.upper()
    for canonical, label in CRM_EMIRATE_LABELS.items():
        if canonical in upper:
            return label

    return cleaned.upper()


def _string_field_value(value: Any) -> str:
    """Return a single string from an Azure field value."""
    if isinstance(value, str):
        return strip_issuing_place_label(value)
    if isinstance(value, dict):
        for key in ("content", "value", "name", "code"):
            nested = value.get(key)
            if isinstance(nested, str) and nested.strip():
                return strip_issuing_place_label(nested)
    for attr in ("content", "value", "name", "code"):
        nested = getattr(value, attr, None)
        if isinstance(nested, str) and nested.strip():
            return strip_issuing_place_label(nested)
    return ""


def _emirate_from_issuing_place_label(lines: list[str]) -> str:
    """Read emirate from Issuing Place label lines in OCR content."""
    for index, line in enumerate(lines):
        match = ISSUING_PLACE_LABEL_RE.match(line)
        if not match:
            continue

        inline = strip_issuing_place_label(match.group(1))
        if inline:
            return inline

        for candidate in lines[index + 1 : index + 4]:
            candidate = normalize_space(candidate)
            if candidate and len(candidate) <= 40:
                detected = _detect_emirate(candidate)
                if detected or candidate.isascii():
                    return candidate

    return ""


def extract_emirate_from_emirates_id_back(
    text: str,
    *,
    existing_fields: dict[str, Any] | None = None,
) -> str:
    """Extract emirate from Emirates ID back Issuing Place field."""
    existing_fields = existing_fields or {}

    for key in ISSUING_PLACE_FIELD_KEYS:
        if key not in existing_fields:
            continue
        raw = _string_field_value(existing_fields[key])
        if raw:
            return normalize_emirate(raw)

    labeled = _emirate_from_issuing_place_label(_lines(text))
    if labeled:
        return normalize_emirate(labeled)

    detected = _detect_emirate(text)
    if detected:
        return CRM_EMIRATE_LABELS.get(detected, detected)

    return ""


def normalize_emirates_id_number(value: str) -> str:
    """Format UAE Emirates ID number as 784-XXXX-XXXXXXX-X."""
    match = EMIRATES_ID_DIGITS_RE.search(value)
    if not match:
        digits = re.sub(r"\D", "", value)
        if len(digits) == 15 and digits.startswith("784"):
            return (
                f"{digits[:3]}-{digits[3:7]}-{digits[7:14]}-{digits[14:]}"
            )
        return ""

    digits = re.sub(r"\D", "", match.group(0))
    if len(digits) == 15:
        return f"{digits[:3]}-{digits[3:7]}-{digits[7:14]}-{digits[14:]}"
    return ""


def _emirates_id_from_fields(existing_fields: dict[str, Any] | None) -> str:
    """Read Emirates ID number from Azure structured fields."""
    if not existing_fields:
        return ""

    for key in EMIRATES_ID_FIELD_KEYS:
        raw = existing_fields.get(key)
        if raw is None:
            continue
        if isinstance(raw, str):
            normalized = normalize_emirates_id_number(raw)
            if normalized:
                return normalized
        if isinstance(raw, dict):
            for nested_key in ("content", "value", "name"):
                nested = raw.get(nested_key)
                if isinstance(nested, str):
                    normalized = normalize_emirates_id_number(nested)
                    if normalized:
                        return normalized
    return ""


def _emirates_id_from_id_number_label(lines: list[str]) -> str:
    """Extract Emirates ID from the ID Number label on the card front."""
    for index, line in enumerate(lines):
        embedded = ID_NUMBER_EMBEDDED_RE.match(line)
        if embedded:
            normalized = normalize_emirates_id_number(embedded.group(1))
            if normalized:
                return normalized

        if ID_NUMBER_LINE_RE.match(line):
            for candidate in lines[index + 1 : index + 4]:
                normalized = normalize_emirates_id_number(candidate)
                if normalized:
                    return normalized

    return ""


def extract_emirates_id_number(
    text: str,
    *,
    existing_fields: dict[str, Any] | None = None,
) -> str:
    """Extract Emirates ID number from Emirates ID front OCR output."""
    existing_fields = existing_fields or {}

    from_fields = _emirates_id_from_fields(existing_fields)
    if from_fields:
        return from_fields

    labeled = _emirates_id_from_id_number_label(_lines(text))
    if labeled:
        return labeled

    inline_match = ID_NUMBER_INLINE_RE.search(text)
    if inline_match:
        return normalize_emirates_id_number(inline_match.group(1))

    card_match = EMIRATES_ID_DIGITS_RE.search(text)
    if card_match:
        return normalize_emirates_id_number(card_match.group(0))

    return ""


def normalize_gender(value: str) -> str:
    """Map Sex field values (M/F) to Male/Female."""
    from apps.ocr.field_transformers import parse_gender

    return parse_gender(value)


def _gender_from_fields(existing_fields: dict[str, Any] | None) -> str:
    """Read gender from Azure Sex field."""
    if not existing_fields:
        return ""

    for key in SEX_FIELD_KEYS:
        raw = existing_fields.get(key)
        if raw is None:
            continue
        if isinstance(raw, str):
            normalized = normalize_gender(raw)
            if normalized in {"Male", "Female"}:
                return normalized
        if isinstance(raw, dict):
            for nested_key in ("content", "value", "name"):
                nested = raw.get(nested_key)
                if isinstance(nested, str):
                    normalized = normalize_gender(nested)
                    if normalized in {"Male", "Female"}:
                        return normalized
    return ""


def _normalize_sex_candidate(candidate: str) -> str:
    """Normalize a Sex value line to Male/Female when possible."""
    cleaned = normalize_space(candidate)
    if not cleaned:
        return ""

    if SEX_VALUE_RE.match(cleaned):
        return normalize_gender(cleaned)

    normalized = normalize_gender(cleaned)
    if normalized in {"Male", "Female"}:
        return normalized

    return ""


def _gender_from_sex_label(lines: list[str]) -> str:
    """Extract gender from Sex label lines in OCR content (bottom of card first)."""
    for index in range(len(lines) - 1, -1, -1):
        line = lines[index]
        embedded = SEX_EMBEDDED_RE.match(line)
        if embedded:
            normalized = _normalize_sex_candidate(embedded.group(1))
            if normalized:
                return normalized

        if SEX_LINE_RE.match(line):
            for candidate in lines[index + 1 : index + 4]:
                normalized = _normalize_sex_candidate(candidate)
                if normalized:
                    return normalized

    return ""


def extract_gender_from_emirates_id(
    text: str,
    *,
    existing_fields: dict[str, Any] | None = None,
) -> str:
    """Extract gender from Emirates ID front Sex field (M/F)."""
    existing_fields = existing_fields or {}
    lines = _lines(text)

    labeled = _gender_from_sex_label(lines)
    if labeled:
        return labeled

    inline_matches = list(SEX_INLINE_RE.finditer(text))
    for match in reversed(inline_matches):
        normalized = normalize_gender(match.group(1))
        if normalized in {"Male", "Female"}:
            return normalized

    return _gender_from_fields(existing_fields)


def extract_nationality_from_emirates_id(
    text: str,
    *,
    existing_fields: dict[str, Any] | None = None,
) -> str:
    """Extract English nationality only from the Emirates ID Nationality field."""
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


def parse_emirates_id_document(
    text: str,
    *,
    existing_fields: dict[str, Any] | None = None,
    document_type: str = "",
) -> dict[str, Any]:
    """Extract Emirates ID fields from OCR output."""
    data: dict[str, Any] = {}
    nationality = extract_nationality_from_emirates_id(
        text,
        existing_fields=existing_fields,
    )
    if nationality:
        data["nationality"] = nationality

    doc_lower = (document_type or "").lower()
    if "emirates_id_front" in doc_lower or doc_lower == "emirates_id":
        emirates_id = extract_emirates_id_number(
            text,
            existing_fields=existing_fields,
        )
        if emirates_id:
            data["emirates_id"] = emirates_id

        gender = extract_gender_from_emirates_id(
            text,
            existing_fields=existing_fields,
        )
        if gender:
            data["gender"] = gender

    if "emirates_id_back" in doc_lower:
        emirate = extract_emirate_from_emirates_id_back(
            text,
            existing_fields=existing_fields,
        )
        if emirate:
            data["emirate"] = emirate

    return data

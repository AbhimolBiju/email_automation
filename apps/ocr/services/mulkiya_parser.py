"""Parse UAE Mulkiya (vehicle registration) text from Azure OCR content."""

from __future__ import annotations

import re
from typing import Any

from documents.ocr_parser import (
    extract_labeled_value,
    extract_vehicle_registration_fields,
    is_noise_line,
    normalize_space,
    parse_date,
)

# Azure keys that may carry Reg. Date (avoid generic RegistrationDate / reg_dt).
REGISTRATION_DATE_FIELD_KEYS: tuple[str, ...] = (
    "RegDate",
    "Reg_Date",
    "reg_date",
)

REG_DATE_ONLY_LABELS: tuple[str, ...] = (
    "reg. date",
    "reg date",
    "تاريخ التسجيل",
)

EXPIRY_DATE_LABELS: tuple[str, ...] = (
    "expiry date",
    "exp. date",
    "date of expiry",
    "date of expiration",
    "expires",
    "valid until",
    "valid to",
    "تاريخ الانتهاء",
)

EXPIRY_DATE_LINE_RE = re.compile(
    r"^(?:Expiry|Exp\.?)\s*Date",
    re.IGNORECASE,
)

REG_DATE_LINE_RE = re.compile(r"^Reg\.?\s*Date\.?$", re.IGNORECASE)
REG_DATE_LABEL_RE = re.compile(r"Reg\.?\s*Date", re.IGNORECASE)
EXP_DATE_LABEL_RE = re.compile(r"(?:Exp\.?|Expiry)\s*Date", re.IGNORECASE)
REGISTRATION_DATE_EMBEDDED_RE = re.compile(
    r"^(?:Registration|Reg\.?)\s*Date\s*[:.\-]?\s*(.+)$",
    re.IGNORECASE,
)
REGISTRATION_DATE_INLINE_RE = re.compile(
    r"(?:Registration|Reg\.?)\s*Date\s*[:.\-]?\s*(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})",
    re.IGNORECASE,
)
REGISTRATION_DATE_ADJACENT_RE = re.compile(
    r"(?:Registration|Reg\.?)\s*Date\s+(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})",
    re.IGNORECASE,
)
REG_DATE_VALUE_BEFORE_LABEL_RE = re.compile(
    r"(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})\s+Reg\.?\s*Date",
    re.IGNORECASE,
)
DATE_TOKEN_RE = re.compile(r"\b\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}\b")

TCF_FIELD_KEYS: tuple[str, ...] = (
    "tcf_number",
    "TCFNumber",
    "TcfNumber",
    "TrafficFileNumber",
    "traffic_file_no",
)

TCF_LABELS: tuple[str, ...] = (
    "t. c. no",
    "t c no",
    "tcf no",
    "traffic file no",
    "traffic file number",
    "رقم الملف",
    "الملف المروري",
)

TCF_EMBEDDED_RE = re.compile(
    r"^(?:T\.?\s*C\.?\s*No|TCF\s*No|Traffic\s*File\s*No)\s*[:.\-]?\s*(.+)$",
    re.IGNORECASE,
)
TCF_LINE_RE = re.compile(r"^T\.?\s*C\.?\s*No\.?$", re.IGNORECASE)
TCF_INLINE_RE = re.compile(
    r"(?:T\.?\s*C\.?\s*No|TCF\s*No|Traffic\s*File\s*No)\s*[:.\-]?\s*(\d[\d\s]{2,14})",
    re.IGNORECASE,
)

REGISTRATION_NUMBER_FIELD_KEYS: tuple[str, ...] = (
    "registration_no",
    "RegistrationNumber",
    "VehicleRegistrationNumber",
    "reg_number",
    "LicensePlate",
    "plate_no",
)

PLATE_CODE_FIELD_KEYS: tuple[str, ...] = (
    "plate_code",
    "traffic_plate_no",
    "plate_category",
)

TRAFFIC_PLATE_LABELS: tuple[str, ...] = (
    "traffic plate no.",
    "traffic plate no",
    "traffic plate number",
    "no. of plate",
    "رقم اللوحة",
)

TRAFFIC_PLATE_EMBEDDED_RE = re.compile(
    r"^(?:Traffic\s*Plate\s*No\.?|Plate\s*No\.?)\s*[:.\-]?\s*(.+)$",
    re.IGNORECASE,
)
TRAFFIC_PLATE_LINE_RE = re.compile(r"^Traffic\s*Plate\s*No\.?$", re.IGNORECASE)
TRAFFIC_PLATE_LABEL_RE = re.compile(r"Traffic\s*Plate\s*No", re.IGNORECASE)
TRAFFIC_PLATE_INLINE_RE = re.compile(
    r"(?:Traffic\s*Plate\s*No\.?|Plate\s*No\.?)\s*[:.\-]?\s*([A-Z0-9][A-Z0-9\s-]{1,14})",
    re.IGNORECASE,
)
TRAFFIC_PLATE_ADJACENT_RE = re.compile(
    r"Traffic\s*Plate\s*No\.?\s+(.+)$",
    re.IGNORECASE,
)

PLATE_SOURCE_FIELD_KEYS: tuple[str, ...] = (
    "PlaceOfIssue",
    "place_of_issue",
    "LicensingAuthority",
    "licensing_authority",
    "plate_source",
    "origin",
    "Region",
    "region",
)

PLACE_OF_ISSUE_LABELS: tuple[str, ...] = (
    "place of issue",
    "licensing authority",
    "مكان الإصدار",
    "جهة الإصدار",
    "جهة الترخيص",
)

PLACE_OF_ISSUE_EMBEDDED_RE = re.compile(
    r"^(?:Place\s*of\s*Issue|Licensing\s*Authority)\s*[:.\-]?\s*(.+)$",
    re.IGNORECASE,
)
PLACE_OF_ISSUE_LINE_RE = re.compile(
    r"^(?:Place\s*of\s*Issue|Licensing\s*Authority)\.?$",
    re.IGNORECASE,
)

ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
ARABIC_DIACRITICS_RE = re.compile(
    r"[\u0640\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]"
)

# Arabic emirate names commonly printed as Place of Issue on Mulkiya cards.
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

PLATE_CATEGORY_RE = re.compile(r"^[A-Z]{1,3}$|^\d{1,2}(?:TH|ST|ND|RD)?\s*CATEGORY$", re.IGNORECASE)
TRAFFIC_PLATE_RE = re.compile(r"^\d{1,6}$")
CHASSIS_RE = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b", re.IGNORECASE)
MODEL_YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")
MODEL_YEAR_ONLY_RE = re.compile(r"^(?:19|20)\d{2}$")

MODEL_YEAR_FIELD_KEYS: tuple[str, ...] = (
    "ModelYear",
    "model_year",
    "Year",
    "year",
)

MODEL_FIELD_KEYS: tuple[str, ...] = (
    "Model",
    "model",
    "model_id",
)


def _lines(text: str) -> list[str]:
    """Return normalized non-empty lines from OCR text."""
    return [normalize_space(line) for line in text.splitlines() if normalize_space(line)]


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

    # Longest Arabic key first so "إمارة دبي" wins over "دبي".
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
        translated = translate_arabic_emirate(cleaned)
        return translated

    detected = _detect_emirate(cleaned)
    if detected:
        return detected

    if cleaned.isascii():
        return cleaned.upper()

    return ""


def _value_after_label(lines: list[str], patterns: tuple[str, ...]) -> str | None:
    """Read the next meaningful line after a label match."""
    for index, line in enumerate(lines):
        lowered = line.lower()
        if not any(pattern in lowered for pattern in patterns):
            continue
        inline = re.split(r"[:\-]", line, maxsplit=1)
        if len(inline) == 2 and normalize_space(inline[1]):
            return normalize_space(inline[1])
        for candidate in lines[index + 1 : index + 4]:
            candidate = normalize_space(candidate)
            if candidate and len(candidate) <= 40:
                return candidate
    return None


def strip_traffic_plate_label(value: str) -> str:
    """Remove duplicated Traffic Plate No label text from OCR/Azure values."""
    cleaned = normalize_space(value)
    if not cleaned:
        return ""

    match = TRAFFIC_PLATE_EMBEDDED_RE.match(cleaned)
    if match:
        return normalize_space(match.group(1)).strip(" .,:;")

    return cleaned.strip(" .,:;")


def normalize_registration_number(value: str) -> str:
    """Normalize a Mulkiya registration (plate number) value."""
    cleaned = strip_traffic_plate_label(value)
    if not cleaned:
        return ""

    token = normalize_space(cleaned).upper()
    combined = re.match(r"^([A-Z]{1,3})\s+(\d{1,8})$", token)
    if combined:
        return combined.group(2)

    if TRAFFIC_PLATE_RE.fullmatch(token):
        return token

    digits = re.sub(r"\D", "", token)
    if digits:
        return digits

    return ""


def normalize_plate_code(value: str) -> str:
    """Normalize a Mulkiya plate code (category/class) value."""
    cleaned = strip_traffic_plate_label(value)
    if not cleaned:
        return ""

    token = normalize_space(cleaned).upper()
    if PLATE_CATEGORY_RE.match(token):
        return token

    combined = re.match(r"^([A-Z]{1,3})\s+(\d{1,8})$", token)
    if combined:
        return combined.group(1)

    return ""


def _split_traffic_plate_tokens(tokens: list[str]) -> tuple[str, str]:
    """Split OCR tokens into plate code and registration number parts."""
    plate_code = ""
    registration_no = ""

    for token in tokens:
        upper = normalize_space(token).upper()
        if not upper:
            continue
        if PLATE_CATEGORY_RE.match(upper):
            plate_code = upper
        elif TRAFFIC_PLATE_RE.fullmatch(upper) or (
            upper.isdigit() and len(upper) >= 2
        ):
            registration_no = upper

    return plate_code, registration_no


def _traffic_plate_tokens_from_text(value: str) -> tuple[str, str]:
    """Parse a Traffic Plate No. value into plate code and registration number."""
    cleaned = strip_traffic_plate_label(value)
    if not cleaned:
        return "", ""

    return _split_traffic_plate_tokens(normalize_space(cleaned).split())


def _traffic_plate_from_azure_layout(
    layout: dict[str, Any] | None,
) -> dict[str, str]:
    """Read plate code and registration number from Traffic Plate No. grid cells."""
    extracted: dict[str, str] = {}
    if not layout:
        return extracted

    lines = layout.get("lines") or []
    for anchor_line in lines:
        content = anchor_line.get("content") or ""
        if not TRAFFIC_PLATE_LABEL_RE.search(content):
            continue

        same_line = TRAFFIC_PLATE_ADJACENT_RE.search(content)
        if same_line:
            plate_code, registration_no = _traffic_plate_tokens_from_text(
                same_line.group(1),
            )
            if plate_code:
                extracted["plate_code"] = plate_code
            if registration_no:
                extracted["registration_no"] = registration_no
            if extracted:
                return extracted

        anchor_box = anchor_line.get("box")
        if not isinstance(anchor_box, dict):
            continue

        row_values: list[tuple[float, str]] = []
        for candidate_line in lines:
            if candidate_line is anchor_line:
                continue
            candidate_content = candidate_line.get("content") or ""
            candidate_box = candidate_line.get("box")
            if not isinstance(candidate_box, dict):
                continue
            if abs(candidate_box["y_center"] - anchor_box["y_center"]) > _row_y_tolerance(
                anchor_box,
                candidate_box,
            ):
                continue
            if candidate_box["x_min"] + 0.01 < anchor_box["x_max"]:
                continue
            row_values.append((candidate_box["x_min"], candidate_content))

        row_values.sort(key=lambda item: item[0])
        tokens: list[str] = []
        for _, row_content in row_values:
            tokens.extend(normalize_space(row_content).split())

        plate_code, registration_no = _split_traffic_plate_tokens(tokens)
        if plate_code:
            extracted["plate_code"] = plate_code
        if registration_no:
            extracted["registration_no"] = registration_no
        if extracted:
            return extracted

    return extracted


def _traffic_plate_from_label_lines(lines: list[str]) -> dict[str, str]:
    """Extract plate code and registration number from Traffic Plate No. label lines."""
    extracted: dict[str, str] = {}

    for index, line in enumerate(lines):
        if not TRAFFIC_PLATE_LABEL_RE.search(line):
            continue

        adjacent = TRAFFIC_PLATE_ADJACENT_RE.search(line)
        if adjacent:
            plate_code, registration_no = _traffic_plate_tokens_from_text(
                adjacent.group(1),
            )
            if plate_code:
                extracted["plate_code"] = plate_code
            if registration_no:
                extracted["registration_no"] = registration_no
            if extracted:
                return extracted

        embedded = TRAFFIC_PLATE_EMBEDDED_RE.match(line)
        if embedded:
            plate_code, registration_no = _traffic_plate_tokens_from_text(
                embedded.group(1),
            )
            if plate_code:
                extracted["plate_code"] = plate_code
            if registration_no:
                extracted["registration_no"] = registration_no
            if extracted:
                return extracted

        value_tokens: list[str] = []
        for candidate in lines[index + 1 : index + 4]:
            if TRAFFIC_PLATE_LABEL_RE.search(candidate):
                break
            value_tokens.extend(normalize_space(candidate).split())

        plate_code, registration_no = _split_traffic_plate_tokens(value_tokens)
        if plate_code:
            extracted["plate_code"] = plate_code
        if registration_no:
            extracted["registration_no"] = registration_no
        if extracted:
            return extracted

    return extracted


def _plate_code_from_fields(existing_fields: dict[str, Any] | None) -> str | None:
    """Read plate code from Azure structured fields."""
    if not existing_fields:
        return None

    for key in PLATE_CODE_FIELD_KEYS:
        raw = existing_fields.get(key)
        if raw is None:
            continue
        if isinstance(raw, str):
            normalized = normalize_plate_code(raw)
            if normalized:
                return normalized
        if isinstance(raw, dict):
            for nested_key in ("content", "value", "name"):
                nested = raw.get(nested_key)
                if isinstance(nested, str):
                    normalized = normalize_plate_code(nested)
                    if normalized:
                        return normalized
    return None


def _extract_traffic_plate_fields(
    text: str,
    lines: list[str],
    *,
    existing_fields: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Extract plate code and registration number from the Traffic Plate No. field."""
    existing_fields = existing_fields or {}
    layout = existing_fields.get("_azure_layout")
    extracted = _traffic_plate_from_azure_layout(layout)
    if not extracted:
        extracted = _traffic_plate_from_label_lines(lines)

    inline_match = TRAFFIC_PLATE_INLINE_RE.search(text)
    if inline_match:
        plate_code, registration_no = _traffic_plate_tokens_from_text(
            inline_match.group(1),
        )
        if plate_code:
            extracted.setdefault("plate_code", plate_code)
        if registration_no:
            extracted.setdefault("registration_no", registration_no)

    plate_code_label = _value_after_label(
        lines,
        (
            "plate code",
            "code",
            "category",
            "plate category",
            "فئة اللوحة",
        ),
    )
    if plate_code_label:
        normalized = normalize_plate_code(plate_code_label)
        if normalized:
            extracted.setdefault("plate_code", normalized)

    plate_code = extracted.get("plate_code") or _plate_code_from_fields(existing_fields)
    if plate_code:
        extracted["plate_code"] = plate_code
        extracted["plate_category"] = plate_code

    extracted = {
        key: value
        for key, value in extracted.items()
        if value not in (None, "")
    }
    return extracted


def _registration_number_from_fields(
    existing_fields: dict[str, Any] | None,
) -> str | None:
    """Read registration number from Azure structured fields."""
    if not existing_fields:
        return None

    for key in REGISTRATION_NUMBER_FIELD_KEYS:
        raw = existing_fields.get(key)
        if raw is None:
            continue
        if isinstance(raw, str):
            normalized = normalize_registration_number(raw)
            if normalized:
                return normalized
        if isinstance(raw, dict):
            for nested_key in ("content", "value", "name"):
                nested = raw.get(nested_key)
                if isinstance(nested, str):
                    normalized = normalize_registration_number(nested)
                    if normalized:
                        return normalized
    return None


def _extract_registration_number(
    text: str,
    lines: list[str],
    *,
    existing_fields: dict[str, Any] | None = None,
    traffic_plate_fields: dict[str, str] | None = None,
) -> str | None:
    """Extract registration number from Azure fields or Traffic Plate No. values row."""
    traffic_plate_fields = traffic_plate_fields or {}
    registration_no = traffic_plate_fields.get("registration_no")
    if registration_no:
        return registration_no

    from_fields = _registration_number_from_fields(existing_fields)
    if from_fields:
        return from_fields

    return None


def _line_is_expiry_label(line: str) -> bool:
    """Return True when the OCR line is an expiry date label, not Reg. Date."""
    lowered = line.lower()
    if EXPIRY_DATE_LINE_RE.match(line):
        return True
    return any(label in lowered for label in EXPIRY_DATE_LABELS)


def strip_registration_date_label(value: str) -> str:
    """Remove duplicated registration date label text from OCR/Azure values."""
    cleaned = normalize_space(value)
    if not cleaned:
        return ""

    match = REGISTRATION_DATE_EMBEDDED_RE.match(cleaned)
    if match:
        return normalize_space(match.group(1)).strip(" .,:;")

    return cleaned.strip(" .,:;")


def _parse_registration_date_value(value: str) -> str | None:
    """Parse a registration date string to ISO format (YYYY-MM-DD)."""
    cleaned = strip_registration_date_label(value)
    if not cleaned:
        return None

    token_match = DATE_TOKEN_RE.search(cleaned)
    if token_match:
        return parse_date(token_match.group(0))

    return parse_date(cleaned)


def _date_tokens_on_line(line: str) -> list[str]:
    """Return all date-like tokens found on a single OCR line."""
    return DATE_TOKEN_RE.findall(normalize_space(line))


def _registration_date_on_same_line_as_reg_label(line: str) -> str | None:
    """Parse the date immediately to the right of a ``Reg. Date`` label on one line."""
    before_label = REG_DATE_VALUE_BEFORE_LABEL_RE.search(line)
    if before_label:
        parsed = parse_date(before_label.group(1))
        if parsed:
            return parsed

    adjacent = REGISTRATION_DATE_ADJACENT_RE.search(line)
    if adjacent:
        parsed = parse_date(adjacent.group(1))
        if parsed:
            return parsed

    match = REG_DATE_LABEL_RE.search(line)
    if not match:
        return None

    tail = line[match.end() :]
    tokens = _date_tokens_on_line(tail)
    if not tokens:
        return None

    return parse_date(tokens[0])


def _row_y_tolerance(reference_box: dict[str, float], other_box: dict[str, float]) -> float:
    """Allow OCR row drift based on the taller of two line boxes."""
    ref_height = max(reference_box.get("height", 0.0), 0.01)
    other_height = max(other_box.get("height", 0.0), 0.01)
    return max(ref_height, other_height) * 0.75


def _registration_date_from_azure_layout(
    layout: dict[str, Any] | None,
) -> str | None:
    """Read the date in the grid cell to the right of the ``Reg. Date`` label."""
    if not layout:
        return None

    lines = layout.get("lines") or []
    for reg_line in lines:
        content = reg_line.get("content") or ""
        if not REG_DATE_LABEL_RE.search(content):
            continue

        same_line = _registration_date_on_same_line_as_reg_label(content)
        if same_line:
            return same_line

        reg_box = reg_line.get("box")
        if not isinstance(reg_box, dict):
            continue

        date_candidates: list[tuple[float, str]] = []
        for candidate_line in lines:
            if candidate_line is reg_line:
                continue
            candidate_content = candidate_line.get("content") or ""
            candidate_box = candidate_line.get("box")
            if not isinstance(candidate_box, dict):
                continue
            if abs(candidate_box["y_center"] - reg_box["y_center"]) > _row_y_tolerance(
                reg_box,
                candidate_box,
            ):
                continue
            if candidate_box["x_min"] + 0.01 < reg_box["x_max"]:
                continue

            for token in _date_tokens_on_line(candidate_content):
                date_candidates.append((candidate_box["x_min"], token))

        if date_candidates:
            date_candidates.sort(key=lambda item: item[0])
            parsed = parse_date(date_candidates[0][1])
            if parsed:
                return parsed

    words = layout.get("words") or []
    reg_anchor: dict[str, Any] | None = None
    for index, word in enumerate(words):
        if not re.match(r"Reg\.?", word.get("content") or "", re.IGNORECASE):
            continue
        phrase = " ".join(
            (words[offset].get("content") or "")
            for offset in range(index, min(index + 3, len(words)))
        )
        if not REG_DATE_LABEL_RE.search(phrase):
            continue
        anchor_box = word.get("box")
        if isinstance(anchor_box, dict):
            for offset in range(index + 1, min(index + 3, len(words))):
                next_box = words[offset].get("box")
                if isinstance(next_box, dict):
                    anchor_box = {
                        "x_min": min(anchor_box["x_min"], next_box["x_min"]),
                        "x_max": max(anchor_box["x_max"], next_box["x_max"]),
                        "y_center": (anchor_box["y_center"] + next_box["y_center"]) / 2,
                        "height": max(
                            anchor_box.get("height", 0.0),
                            next_box.get("height", 0.0),
                        ),
                    }
            reg_anchor = {"box": anchor_box}
            break

    if reg_anchor:
        anchor_box = reg_anchor["box"]
        word_candidates: list[tuple[float, str]] = []
        for word in words:
            content = word.get("content") or ""
            if not DATE_TOKEN_RE.fullmatch(content):
                continue
            box = word.get("box")
            if not isinstance(box, dict):
                continue
            if box["x_min"] + 0.01 < anchor_box["x_max"]:
                continue
            if abs(box["y_center"] - anchor_box["y_center"]) > _row_y_tolerance(
                anchor_box,
                box,
            ):
                continue
            word_candidates.append((box["x_min"], content))

        if word_candidates:
            word_candidates.sort(key=lambda item: item[0])
            parsed = parse_date(word_candidates[0][1])
            if parsed:
                return parsed

    return None


def _pick_registration_date_from_tokens(
    tokens: list[str],
    *,
    reg_pos: int,
    exp_pos: int | None,
) -> str | None:
    """Pick the registration date when Exp. Date and Reg. Date share one values row."""
    if not tokens:
        return None

    if len(tokens) == 1:
        return parse_date(tokens[0])

    if exp_pos is None:
        return parse_date(tokens[-1])

    if reg_pos > exp_pos:
        return parse_date(tokens[-1])
    return parse_date(tokens[0])


def _registration_date_from_reg_date_layout(lines: list[str]) -> str | None:
    """Extract registration date from paired Exp./Reg. Date columns on Mulkiya front."""
    for index, line in enumerate(lines):
        reg_match = REG_DATE_LABEL_RE.search(line)
        if not reg_match:
            continue

        same_line = _registration_date_on_same_line_as_reg_label(line)
        if same_line:
            return same_line

        header_context = " ".join(lines[max(0, index - 2) : index + 1])
        exp_match = EXP_DATE_LABEL_RE.search(header_context)
        reg_pos = reg_match.start()
        if exp_match:
            reg_pos = header_context.find(reg_match.group(0))
            exp_pos = header_context.find(exp_match.group(0))
        else:
            exp_pos = None

        for offset in range(1, 4):
            candidate_index = index + offset
            if candidate_index >= len(lines):
                break
            candidate = lines[candidate_index]
            if _line_is_expiry_label(candidate) and not _date_tokens_on_line(candidate):
                continue

            tokens = _date_tokens_on_line(candidate)
            if not tokens:
                continue

            parsed = _pick_registration_date_from_tokens(
                tokens,
                reg_pos=reg_pos,
                exp_pos=exp_pos,
            )
            if parsed:
                return parsed

    return None


def _registration_date_from_fields(
    existing_fields: dict[str, Any] | None,
) -> str | None:
    """Read registration date from Azure structured fields."""
    if not existing_fields:
        return None

    expiry_value = None
    for expiry_key in (
        "ExpiryDate",
        "expiry_date",
        "DateOfExpiration",
        "expiration_date",
    ):
        raw_expiry = existing_fields.get(expiry_key)
        if isinstance(raw_expiry, str):
            expiry_value = _parse_registration_date_value(raw_expiry)
            if expiry_value:
                break

    for key in REGISTRATION_DATE_FIELD_KEYS:
        raw = existing_fields.get(key)
        if raw is None:
            continue
        if isinstance(raw, str):
            parsed = _parse_registration_date_value(raw)
            if parsed and parsed != expiry_value:
                return parsed
        if isinstance(raw, dict):
            for nested_key in ("content", "value", "name"):
                nested = raw.get(nested_key)
                if isinstance(nested, str):
                    parsed = _parse_registration_date_value(nested)
                    if parsed and parsed != expiry_value:
                        return parsed
    return None


def _registration_date_from_reg_date_label(lines: list[str]) -> str | None:
    """Extract registration date from the Mulkiya ``Reg. Date`` label."""
    layout_date = _registration_date_from_reg_date_layout(lines)
    if layout_date:
        return layout_date

    for index, line in enumerate(lines):
        if _line_is_expiry_label(line) and not REG_DATE_LABEL_RE.search(line):
            continue

        adjacent = REGISTRATION_DATE_ADJACENT_RE.search(line)
        if adjacent:
            parsed = _parse_registration_date_value(adjacent.group(1))
            if parsed:
                return parsed

        embedded = REGISTRATION_DATE_EMBEDDED_RE.match(line)
        if embedded:
            remainder = normalize_space(embedded.group(1))
            if remainder:
                parsed = _parse_registration_date_value(remainder)
                if parsed:
                    return parsed

        if REG_DATE_LINE_RE.match(line) or (
            REG_DATE_LABEL_RE.search(line)
            and not _date_tokens_on_line(line)
        ):
            for candidate in lines[index - 1 : index][::-1]:
                if _line_is_expiry_label(candidate):
                    continue
                tokens = _date_tokens_on_line(candidate)
                if len(tokens) == 1:
                    parsed = parse_date(tokens[0])
                    if parsed:
                        return parsed

            for candidate in lines[index + 1 : index + 4]:
                if _line_is_expiry_label(candidate):
                    continue
                tokens = _date_tokens_on_line(candidate)
                if len(tokens) >= 2:
                    parsed = parse_date(tokens[-1])
                    if parsed:
                        return parsed
                parsed = _parse_registration_date_value(candidate)
                if parsed:
                    return parsed

    return None


def _extract_registration_date(
    text: str,
    lines: list[str],
    *,
    existing_fields: dict[str, Any] | None = None,
) -> str | None:
    """Extract registration date only from the Mulkiya ``Reg. Date`` label."""
    layout = (existing_fields or {}).get("_azure_layout")
    layout_date = _registration_date_from_azure_layout(layout)
    if layout_date:
        return layout_date

    before_label = REG_DATE_VALUE_BEFORE_LABEL_RE.search(text)
    if before_label:
        parsed = parse_date(before_label.group(1))
        if parsed:
            return parsed

    # Reg. Date label always wins over Azure/generic fields (prevents expiry confusion).
    reg_date = _registration_date_from_reg_date_label(lines)
    if reg_date:
        return reg_date

    for line in lines:
        if _line_is_expiry_label(line):
            continue
        adjacent = REGISTRATION_DATE_ADJACENT_RE.search(line)
        if adjacent:
            parsed = _parse_registration_date_value(adjacent.group(1))
            if parsed:
                return parsed

        embedded = REGISTRATION_DATE_EMBEDDED_RE.match(line)
        if embedded and not _line_is_expiry_label(line):
            remainder = normalize_space(embedded.group(1))
            if remainder:
                parsed = _parse_registration_date_value(remainder)
                if parsed:
                    return parsed

    inline_match = REGISTRATION_DATE_INLINE_RE.search(text)
    if inline_match:
        parsed = _parse_registration_date_value(inline_match.group(1))
        if parsed:
            return parsed

    labeled = _value_after_label(lines, REG_DATE_ONLY_LABELS)
    if labeled and not _line_is_expiry_label(labeled):
        parsed = _parse_registration_date_value(labeled)
        if parsed:
            return parsed

    return _registration_date_from_fields(existing_fields)


def _plate_source_from_fields(existing_fields: dict[str, Any] | None) -> str | None:
    """Read plate source from Azure structured fields."""
    if not existing_fields:
        return None

    for key in PLATE_SOURCE_FIELD_KEYS:
        raw = existing_fields.get(key)
        if raw is None:
            continue
        if isinstance(raw, str):
            normalized = normalize_plate_source(raw)
            if normalized:
                return normalized
        if isinstance(raw, dict):
            for nested_key in ("content", "value", "name"):
                nested = raw.get(nested_key)
                if isinstance(nested, str):
                    normalized = normalize_plate_source(nested)
                    if normalized:
                        return normalized
    return None


def _plate_source_from_place_of_issue_label(lines: list[str]) -> str | None:
    """Extract plate source from the Mulkiya Place of Issue label."""
    for index, line in enumerate(lines):
        embedded = PLACE_OF_ISSUE_EMBEDDED_RE.match(line)
        if embedded:
            remainder = normalize_space(embedded.group(1))
            if remainder:
                normalized = normalize_plate_source(remainder)
                if normalized:
                    return normalized

        if PLACE_OF_ISSUE_LINE_RE.match(line):
            for candidate in lines[index + 1 : index + 4]:
                normalized = normalize_plate_source(candidate)
                if normalized:
                    return normalized

    return None


def _extract_plate_source(
    text: str,
    lines: list[str],
    *,
    existing_fields: dict[str, Any] | None = None,
) -> str | None:
    """Extract plate source from Mulkiya front Place of Issue field."""
    from_fields = _plate_source_from_fields(existing_fields)
    if from_fields:
        return from_fields

    labeled = _plate_source_from_place_of_issue_label(lines)
    if labeled:
        return labeled

    place_of_issue = _value_after_label(lines, PLACE_OF_ISSUE_LABELS)
    if place_of_issue:
        normalized = normalize_plate_source(place_of_issue)
        if normalized:
            return normalized

    return _detect_emirate(normalize_space(text))


def strip_tcf_label(value: str) -> str:
    """Remove duplicated T. C. No label text from OCR/Azure values."""
    cleaned = normalize_space(value)
    if not cleaned:
        return ""

    match = TCF_EMBEDDED_RE.match(cleaned)
    if match:
        return normalize_space(match.group(1)).strip(" .,:;")

    return cleaned.strip(" .,:;")


def normalize_tcf_number(value: str) -> str:
    """Normalize traffic file (TCF) number digits."""
    cleaned = strip_tcf_label(value)
    if not cleaned:
        return ""

    digits = re.sub(r"\D", "", cleaned)
    if len(digits) >= 3:
        return digits

    return ""


def _tcf_from_fields(existing_fields: dict[str, Any] | None) -> str | None:
    """Read TCF number from Azure structured fields."""
    if not existing_fields:
        return None

    for key in TCF_FIELD_KEYS:
        raw = existing_fields.get(key)
        if raw is None:
            continue
        if isinstance(raw, str):
            normalized = normalize_tcf_number(raw)
            if normalized:
                return normalized
        if isinstance(raw, dict):
            for nested_key in ("content", "value", "name"):
                nested = raw.get(nested_key)
                if isinstance(nested, str):
                    normalized = normalize_tcf_number(nested)
                    if normalized:
                        return normalized
    return None


def _tcf_from_label_lines(lines: list[str]) -> str | None:
    """Extract TCF number from T. C. No label lines in OCR content."""
    for index, line in enumerate(lines):
        embedded = TCF_EMBEDDED_RE.match(line)
        if embedded:
            remainder = normalize_space(embedded.group(1))
            if remainder:
                normalized = normalize_tcf_number(remainder)
                if normalized:
                    return normalized

        if TCF_LINE_RE.match(line):
            for candidate in lines[index + 1 : index + 4]:
                normalized = normalize_tcf_number(candidate)
                if normalized:
                    return normalized

    labeled = extract_labeled_value(lines, TCF_LABELS)
    if labeled:
        return normalize_tcf_number(labeled) or None

    return None


def _extract_tcf_number(
    text: str,
    lines: list[str],
    *,
    existing_fields: dict[str, Any] | None = None,
) -> str | None:
    """Extract traffic file (TCF) number from Mulkiya front OCR output."""
    from_fields = _tcf_from_fields(existing_fields)
    if from_fields:
        return from_fields

    labeled = _tcf_from_label_lines(lines)
    if labeled:
        return labeled

    inline_match = TCF_INLINE_RE.search(text)
    if inline_match:
        return normalize_tcf_number(inline_match.group(1)) or None

    return None


def parse_mulkiya_front(
    text: str,
    *,
    existing_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Extract deal fields from the front side of a Mulkiya card."""
    normalized = normalize_space(text)
    lines = _lines(text)
    data: dict[str, Any] = dict(extract_vehicle_registration_fields(lines, text))

    traffic_plate_fields = _extract_traffic_plate_fields(
        normalized,
        lines,
        existing_fields=existing_fields,
    )
    plate_code = traffic_plate_fields.get("plate_code")
    if plate_code:
        data["plate_code"] = plate_code
        data["traffic_plate_no"] = plate_code
        data["plate_category"] = traffic_plate_fields.get("plate_category", plate_code)

    plate_source = _extract_plate_source(
        normalized,
        lines,
        existing_fields=existing_fields,
    )
    if plate_source:
        data["plate_source"] = plate_source

    registration_no = _extract_registration_number(
        normalized,
        lines,
        existing_fields=existing_fields,
        traffic_plate_fields=traffic_plate_fields,
    )
    if registration_no:
        data["registration_no"] = registration_no

    if data.get("plate_no") and not data.get("registration_no"):
        data["registration_no"] = data["plate_no"]

    registration_date = _extract_registration_date(
        normalized,
        lines,
        existing_fields=existing_fields,
    )
    if registration_date:
        data["registration_date"] = registration_date
        data["RegDate"] = registration_date
        data["reg_date"] = registration_date

    tcf_number = _extract_tcf_number(
        normalized,
        lines,
        existing_fields=existing_fields,
    )
    if tcf_number:
        data["tcf_number"] = tcf_number

    return {key: value for key, value in data.items() if value not in (None, "")}


def _split_model_and_year(value: str) -> tuple[str, str | None]:
    """Split a combined model/year OCR token into separate values."""
    cleaned = normalize_space(value)
    if not cleaned:
        return "", None

    if MODEL_YEAR_ONLY_RE.fullmatch(cleaned):
        return "", cleaned

    year_match = MODEL_YEAR_RE.search(cleaned)
    if not year_match:
        return cleaned, None

    year = year_match.group(1)
    model = normalize_space(MODEL_YEAR_RE.sub("", cleaned)).strip(" -,/")
    return model, year


def _string_field_value(value: Any) -> str:
    """Return a single string from an Azure field value."""
    if isinstance(value, str):
        return normalize_space(value)
    if isinstance(value, dict):
        for key in ("content", "value", "name"):
            nested = value.get(key)
            if isinstance(nested, str) and nested.strip():
                return normalize_space(nested)
    for attr in ("content", "value", "name"):
        nested = getattr(value, attr, None)
        if isinstance(nested, str) and nested.strip():
            return normalize_space(nested)
    return ""


def _model_year_from_fields(existing_fields: dict[str, Any] | None) -> str | None:
    """Read model year from Azure structured fields."""
    if not existing_fields:
        return None

    for key in MODEL_YEAR_FIELD_KEYS:
        raw = _string_field_value(existing_fields.get(key))
        if raw and MODEL_YEAR_ONLY_RE.fullmatch(raw):
            return raw

    for key in MODEL_FIELD_KEYS:
        raw = _string_field_value(existing_fields.get(key))
        if not raw:
            continue
        _, year = _split_model_and_year(raw)
        if year:
            return year

    return None


def _model_from_fields(existing_fields: dict[str, Any] | None) -> str | None:
    """Read vehicle model from Azure structured fields."""
    if not existing_fields:
        return None

    for key in MODEL_FIELD_KEYS:
        raw = _string_field_value(existing_fields.get(key))
        if not raw:
            continue
        model, _year = _split_model_and_year(raw)
        if model and not MODEL_YEAR_ONLY_RE.fullmatch(model):
            return model

    return None


def _extract_vehicle_model_and_year(
    lines: list[str],
    *,
    existing_fields: dict[str, Any] | None = None,
) -> tuple[str | None, str | None]:
    """Extract vehicle model and year from the ``Model`` label on Mulkiya back."""
    model = _model_from_fields(existing_fields)
    year = _model_year_from_fields(existing_fields)

    labeled = extract_labeled_value(lines, ("model", "vehicle model", "موديل", "الطراز"))
    if labeled:
        split_model, split_year = _split_model_and_year(labeled)
        model = model or split_model or None
        year = year or split_year

    for index, line in enumerate(lines):
        if re.search(r"\bmodel\s+year\b", line, re.IGNORECASE):
            inline_year = re.match(r"^model\s+year\s*[:\-]?\s*(.+)$", line, re.IGNORECASE)
            if inline_year:
                candidate = normalize_space(inline_year.group(1))
                if MODEL_YEAR_ONLY_RE.fullmatch(candidate):
                    year = year or candidate
            continue

        inline = re.match(r"^model\s*[:\-]?\s*(.+)$", line, re.IGNORECASE)
        if inline:
            split_model, split_year = _split_model_and_year(inline.group(1))
            model = model or split_model or None
            year = year or split_year
            continue

        if re.fullmatch(r"model", line, re.IGNORECASE):
            for candidate in lines[index + 1 : index + 5]:
                candidate = normalize_space(candidate)
                if (
                    not candidate
                    or is_noise_line(candidate)
                    or re.fullmatch(r"model", candidate, re.IGNORECASE)
                ):
                    continue

                if MODEL_YEAR_ONLY_RE.fullmatch(candidate):
                    year = year or candidate
                    continue

                split_model, split_year = _split_model_and_year(candidate)
                if split_model and not model:
                    model = split_model
                if split_year and not year:
                    year = split_year

    return model, year


def parse_mulkiya_back(
    text: str,
    *,
    existing_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Extract deal fields from the back side of a Mulkiya card (chassis/VIN)."""
    normalized = normalize_space(text)
    lines = _lines(text)
    data: dict[str, Any] = dict(extract_vehicle_registration_fields(lines, text))

    chassis_match = CHASSIS_RE.search(normalized)
    if chassis_match:
        data["chassis_no"] = chassis_match.group(0).upper()

    vehicle_model, model_year = _extract_vehicle_model_and_year(
        lines,
        existing_fields=existing_fields,
    )
    if vehicle_model:
        data["model_id"] = vehicle_model
        data["model"] = vehicle_model
    if model_year:
        data["model_year"] = model_year
        data["year"] = model_year

    return {key: value for key, value in data.items() if value not in (None, "")}


def parse_mulkiya_document(
    text: str,
    *,
    document_type: str,
    existing_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Route Mulkiya parsing based on upload slot (front vs back)."""
    normalized_type = (document_type or "").lower()
    if normalized_type.endswith("_back"):
        return parse_mulkiya_back(text, existing_fields=existing_fields)
    return parse_mulkiya_front(text, existing_fields=existing_fields)

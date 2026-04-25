import re
from datetime import datetime
from typing import Any


DATE_FORMATS = (
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%d %b %Y",
    "%d %B %Y",
    "%b %d, %Y",
    "%B %d, %Y",
)


FIELD_ALIASES = {
    "full_name": (
        "name",
        "full name",
        "card holder",
        "holder name",
        "customer name",
        "insured name",
        "insured full name",
    ),
    "nationality": ("nationality", "nation"),
    "expiry_date": (
        "expiry date",
        "date of expiry",
        "expires",
        "valid until",
        "valid to",
    ),
    "issue_date": ("issue date", "date of issue", "issued on", "valid from"),
    "dob": ("date of birth", "birth date", "dob"),
    "address": ("address", "residence", "place of residence"),
    "license_no": ("license no", "licence no", "driving license", "license number"),
    "passport_no": ("passport no", "passport number"),
    "plate_no": ("plate no", "plate number", "registration no", "reg no"),
    "policy_no": ("policy no", "policy number", "certificate no"),
    "invoice_no": ("invoice no", "invoice number", "tax invoice"),
    "chassis_no": ("chassis no", "chassis number", "vin", "vehicle identification"),
    "engine_no": ("engine no", "engine number"),
}


DOCUMENT_TYPE_KEYWORDS = (
    ("emirates_id", ("emirates id", "identity card", "united arab emirates")),
    ("passport", ("passport",)),
    ("driving_license", ("driving license", "driving licence", "driver license")),
    ("vehicle_registration", ("vehicle registration", "mulkiya", "traffic file", "chassis")),
    ("insurance_policy", ("insurance policy", "policy schedule", "certificate of insurance")),
    ("invoice", ("invoice", "tax invoice", "vat invoice")),
)


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def parse_date(value: str) -> str | None:
    cleaned = normalize_space(value).replace(",", "")
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt.replace(",", "")).date().isoformat()
        except ValueError:
            continue
    match = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b", cleaned)
    if not match:
        return None
    day, month, year = match.groups()
    if len(year) == 2:
        year = f"19{year}" if int(year) > 30 else f"20{year}"
    try:
        return datetime(int(year), int(month), int(day)).date().isoformat()
    except ValueError:
        return None


def detect_document_type(text: str, fallback: str = "other") -> str:
    lowered = text.lower()
    for document_type, keywords in DOCUMENT_TYPE_KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            return document_type
    return fallback or "other"


def extract_labeled_value(lines: list[str], aliases: tuple[str, ...]) -> str | None:
    for index, line in enumerate(lines):
        lowered = line.lower()
        for alias in aliases:
            if alias not in lowered:
                continue

            same_line = re.split(r"[:\-]", line, maxsplit=1)
            if len(same_line) == 2 and normalize_space(same_line[1]):
                return normalize_space(same_line[1])

            if index + 1 < len(lines):
                next_line = normalize_space(lines[index + 1])
                if next_line and not any(next_line.lower().startswith(a) for a in aliases):
                    return next_line
    return None


def extract_dates(text: str) -> list[str]:
    candidates = re.findall(
        r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{1,2}-\d{1,2}|"
        r"\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}|[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})\b",
        text,
    )
    parsed: list[str] = []
    for candidate in candidates:
        value = parse_date(candidate)
        if value and value not in parsed:
            parsed.append(value)
    return parsed


def extract_label_values(lines: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in lines:
        match = re.match(r"^([A-Za-z][A-Za-z0-9 /_.()-]{2,40})\s*[:\-]\s*(.+)$", line)
        if not match:
            continue
        key = re.sub(r"[^a-z0-9]+", "_", match.group(1).lower()).strip("_")
        value = normalize_space(match.group(2))
        if key and value:
            values[key] = value
    return values


def extract_structured_fields(
    text: str,
    *,
    confidence: float | None = None,
    document_type_hint: str = "other",
) -> dict[str, Any]:
    normalized_text = normalize_space(text)
    lines = [normalize_space(line) for line in text.splitlines() if normalize_space(line)]
    detected_type = detect_document_type(normalized_text, document_type_hint)

    extracted: dict[str, Any] = {
        "document_type": detected_type,
        "raw_text": text,
        "confidence": confidence,
    }
    label_values = extract_label_values(lines)
    if label_values:
        extracted["label_values"] = label_values

    for field, aliases in FIELD_ALIASES.items():
        value = extract_labeled_value(lines, aliases)
        if not value:
            continue
        extracted[field] = parse_date(value) if field.endswith("date") or field == "dob" else value

    emirates_match = re.search(r"\b784[-\s]?\d{4}[-\s]?\d{7}[-\s]?\d\b", normalized_text)
    if emirates_match:
        digits = re.sub(r"\D", "", emirates_match.group(0))
        extracted["emirates_id"] = f"{digits[:3]}-{digits[3:7]}-{digits[7:14]}-{digits[14:]}"

    if "passport_no" not in extracted:
        passport_match = re.search(r"\b[A-Z][0-9]{7,9}\b", normalized_text, re.IGNORECASE)
        if passport_match:
            extracted["passport_no"] = passport_match.group(0).upper()

    if "license_no" not in extracted:
        license_match = re.search(
            r"\b(?:license|licence)\s*(?:no|number)?\s*[:\-]?\s*([A-Z0-9/-]{4,20})",
            normalized_text,
            re.IGNORECASE,
        )
        if license_match:
            extracted["license_no"] = license_match.group(1).upper()

    if "plate_no" not in extracted:
        plate_match = re.search(
            r"\b(?:plate|registration|reg)\s*(?:no|number)?\s*[:\-]?\s*([A-Z0-9 -]{2,15})",
            normalized_text,
            re.IGNORECASE,
        )
        if plate_match:
            extracted["plate_no"] = normalize_space(plate_match.group(1)).upper()

    dates = extract_dates(normalized_text)
    if dates:
        extracted.setdefault("dates_found", dates)

    return {key: value for key, value in extracted.items() if value not in (None, "")}

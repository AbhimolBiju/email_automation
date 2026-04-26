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
    "emirates_id": ("emirates id", "id number", "identity number"),
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
    "manufacturer": ("manufacturer", "make", "vehicle make"),
    "model": ("model", "vehicle model"),
    "year": ("year", "model year"),
    "origin": ("origin", "country of origin"),
    "color": ("color", "colour"),
    "amount": ("amount", "total", "invoice total", "premium"),
    "tax_registration_no": ("trn", "tax registration number"),
}


DOCUMENT_TYPE_KEYWORDS = (
    ("emirates_id", ("emirates id", "identity card", "united arab emirates")),
    ("passport", ("passport",)),
    ("driving_license", ("driving license", "driving licence", "driver license")),
    ("insurance_policy", ("insurance policy", "policy schedule", "certificate of insurance")),
    ("invoice", ("invoice", "tax invoice", "vat invoice")),
    ("vehicle_registration", ("vehicle registration", "mulkiya", "traffic file", "chassis")),
)

ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
VEHICLE_LABEL_RE = re.compile(
    r"(vehicle information|num\.?\s*of\s*pass|model|veh\.?\s*type|empty weight|"
    r"g\.?\s*v\.?\s*w\.?|eng\.?\s*no|chassis\s*no|origin|licensing authority|"
    r"changes to vehicle|بيانات المركبة|عدد الركاب|سنة الصنع|صنف المركبة|"
    r"رقم المحرك|رقم القاعدة|بلد الصنع|لون المركبة|نوع المركبة|الوزن)",
    re.IGNORECASE,
)
KNOWN_MANUFACTURERS = (
    "MITSUBISHI",
    "TOYOTA",
    "NISSAN",
    "HONDA",
    "HYUNDAI",
    "KIA",
    "FORD",
    "CHEVROLET",
    "BMW",
    "MERCEDES",
    "AUDI",
    "LEXUS",
    "MAZDA",
    "VOLKSWAGEN",
    "JEEP",
    "LAND ROVER",
    "PORSCHE",
    "SUZUKI",
    "RENAULT",
    "PEUGEOT",
)
COLOR_TRANSLATIONS = {
    "ابيض": "White",
    "أبيض": "White",
    "اسود": "Black",
    "أسود": "Black",
    "احمر": "Red",
    "أحمر": "Red",
    "ازرق": "Blue",
    "أزرق": "Blue",
    "فضي": "Silver",
    "رمادي": "Grey",
    "اخضر": "Green",
    "أخضر": "Green",
}
ORIGIN_TRANSLATIONS = {
    "اليابان": "Japan",
}


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

            same_line = re.match(r"^.*?\b" + re.escape(alias) + r"\b\s*[:\-]?\s*(.+)$", line, re.IGNORECASE)
            if same_line and normalize_space(same_line.group(1)):
                return normalize_space(same_line.group(1))

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


def has_arabic(value: str) -> bool:
    return bool(ARABIC_RE.search(value))


def latin_ratio(value: str) -> float:
    letters = re.findall(r"[A-Za-z\u0600-\u06FF]", value)
    if not letters:
        return 0
    latin = re.findall(r"[A-Za-z]", value)
    return len(latin) / len(letters)


def is_noise_line(value: str) -> bool:
    value = normalize_space(value)
    if not value:
        return True
    if VEHICLE_LABEL_RE.search(value):
        return True
    if has_arabic(value) and latin_ratio(value) == 0 and value not in COLOR_TRANSLATIONS and value not in ORIGIN_TRANSLATIONS:
        return True
    return False


def nearby_value_before_label(lines: list[str], label_pattern: str, *, max_lookback: int = 3) -> str | None:
    label_re = re.compile(label_pattern, re.IGNORECASE)
    for index, line in enumerate(lines):
        if not label_re.search(line):
            continue
        for candidate in reversed(lines[max(0, index - max_lookback):index]):
            candidate = normalize_space(candidate)
            if not is_noise_line(candidate):
                return candidate
    return None


def nearby_value_after_label(lines: list[str], label_pattern: str, *, max_lookahead: int = 3) -> str | None:
    label_re = re.compile(label_pattern, re.IGNORECASE)
    for index, line in enumerate(lines):
        if not label_re.search(line):
            continue
        for candidate in lines[index + 1:index + 1 + max_lookahead]:
            candidate = normalize_space(candidate)
            if not is_noise_line(candidate):
                return candidate
    return None


def first_match(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1 if match.groups() else 0).strip() if match else None


def clean_engine_no(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def clean_vehicle_name(value: str) -> str | None:
    value = clean_identifier(value, max_length=80)
    if not re.search(r"[A-Z]", value):
        return None
    if VEHICLE_LABEL_RE.search(value):
        return None
    if re.fullmatch(r"[0-9 ]+", value):
        return None
    return value


def split_vehicle_name(vehicle_name: str) -> tuple[str | None, str | None]:
    for manufacturer in KNOWN_MANUFACTURERS:
        if vehicle_name == manufacturer:
            return manufacturer, None
        if vehicle_name.startswith(f"{manufacturer} "):
            return manufacturer, vehicle_name[len(manufacturer):].strip()
    parts = vehicle_name.split()
    if len(parts) >= 2:
        return parts[0], " ".join(parts[1:])
    return vehicle_name, None


def extract_vehicle_registration_fields(lines: list[str], text: str) -> dict[str, str]:
    data: dict[str, str] = {"document_type": "vehicle_registration"}
    normalized_text = normalize_space(text)

    passenger_capacity = nearby_value_before_label(lines, r"num\.?\s*of\s*pass|عدد الركاب")
    if passenger_capacity:
        match = re.search(r"\b\d{1,2}\b", passenger_capacity)
        if match:
            data["passenger_capacity"] = match.group(0)

    year = nearby_value_after_label(lines, r"سنة الصنع") or nearby_value_before_label(lines, r"\bmodel\b")
    if year:
        year_match = re.search(r"\b(19|20)\d{2}\b", year)
        if year_match:
            data["year"] = year_match.group(0)

    engine = nearby_value_before_label(lines, r"\beng\.?\s*no\b|engine\s*no")
    if not engine:
        engine = nearby_value_after_label(lines, r"رقم المحرك")
    if engine:
        cleaned_engine = clean_engine_no(engine)
        if len(cleaned_engine) >= 5:
            data["engine_no"] = cleaned_engine

    chassis = nearby_value_before_label(lines, r"chassis\s*no")
    if not chassis:
        chassis = nearby_value_after_label(lines, r"رقم القاعدة")
    if not chassis:
        chassis = first_match(r"\b([A-HJ-NPR-Z0-9]{17})\b", normalized_text)
    if chassis:
        normalized_chassis = normalize_field_value("chassis_no", chassis)
        if normalized_chassis:
            data["chassis_no"] = normalized_chassis

    origin = nearby_value_before_label(lines, r"\borigin\b")
    if not origin:
        origin = nearby_value_after_label(lines, r"بلد الصنع")
    if origin:
        data["origin"] = ORIGIN_TRANSLATIONS.get(origin, origin)
    elif any(line in ORIGIN_TRANSLATIONS for line in lines):
        data["origin"] = ORIGIN_TRANSLATIONS[next(line for line in lines if line in ORIGIN_TRANSLATIONS)]

    color = nearby_value_after_label(lines, r"\borigin\b|بلد الصنع|لون المركبة", max_lookahead=5)
    if color:
        data["color"] = COLOR_TRANSLATIONS.get(color, color)

    vehicle_candidates = [
        clean_vehicle_name(line)
        for line in lines
        if clean_vehicle_name(line) and len(line.split()) >= 2
    ]
    if vehicle_candidates:
        vehicle_name = max(vehicle_candidates, key=lambda value: (any(m in value for m in KNOWN_MANUFACTURERS), len(value)))
        data["vehicle_name"] = vehicle_name
        manufacturer, model = split_vehicle_name(vehicle_name)
        if manufacturer:
            data["manufacturer"] = manufacturer
        if model:
            data["model"] = model

    return data


def clean_identifier(value: str, *, max_length: int = 40) -> str:
    return normalize_space(value).strip(" .,:;").upper()[:max_length]


def normalize_field_value(field: str, value: str) -> str | None:
    value = normalize_space(value)
    if field.endswith("date") or field == "dob":
        return parse_date(value)
    if field == "emirates_id":
        digits = re.sub(r"\D", "", value)
        if len(digits) == 15 and digits.startswith("784"):
            return f"{digits[:3]}-{digits[3:7]}-{digits[7:14]}-{digits[14:]}"
        return None
    if field == "chassis_no":
        match = re.search(r"\b[A-HJ-NPR-Z0-9]{17}\b", value, re.IGNORECASE)
        return match.group(0).upper() if match else None
    if field in {"engine_no", "license_no", "passport_no", "plate_no", "policy_no", "invoice_no"}:
        return clean_identifier(value)
    if field == "year":
        match = re.search(r"\b(19|20)\d{2}\b", value)
        return match.group(0) if match else None
    return value


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
    }
    label_values = extract_label_values(lines)

    if detected_type == "vehicle_registration":
        extracted.update(extract_vehicle_registration_fields(lines, text))

    for field, aliases in FIELD_ALIASES.items():
        if field in extracted:
            continue
        value = extract_labeled_value(lines, aliases)
        if not value:
            continue
        normalized_value = normalize_field_value(field, value)
        if normalized_value:
            extracted[field] = normalized_value

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

    if "chassis_no" not in extracted:
        vin_match = re.search(r"\b[A-HJ-NPR-Z0-9]{17}\b", normalized_text, re.IGNORECASE)
        if vin_match:
            extracted["chassis_no"] = vin_match.group(0).upper()

    if "engine_no" not in extracted:
        engine_match = re.search(
            r"\b(?:engine)\s*(?:no|number)?\s*[:\-]?\s*([A-Z0-9]{5,25})",
            normalized_text,
            re.IGNORECASE,
        )
        if engine_match:
            extracted["engine_no"] = engine_match.group(1).upper()

    dates = extract_dates(normalized_text)
    if dates:
        extracted.setdefault("dates_found", dates)

    additional_fields = {
        key: value
        for key, value in label_values.items()
        if key not in extracted and key not in {"raw_text", "confidence", "engine", "model_id"}
    }
    if additional_fields:
        extracted["additional_fields"] = additional_fields

    return {key: value for key, value in extracted.items() if value not in (None, "")}

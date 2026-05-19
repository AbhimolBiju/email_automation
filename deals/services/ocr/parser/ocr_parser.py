import re
from datetime import datetime
from typing import Any

DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%d/%m/%y",
    "%d-%m-%y",
    "%m/%d/%Y",
    "%d %b %Y",
    "%d %B %Y",
    "%b %d %Y",
    "%B %d %Y",
)


FIELD_ALIASES = {

    "customer_name": (
        "customer name",
        "full name",
        "holder name",
        "insured name",
    ),

    "nationality": (
        "nationality",
        "nation",
    ),

    "emirates_id": (
        "emirates id",
        "id number",
        "identity number",
    ),

    "id_expiry_date": (
        "id-expiry date",
        "id expiry date",
        "expiry date",
        "date of expiry",
        "valid until",
    ),

    "date_of_birth": (
        "date of birth",
        "dob",
        "birth date",
    ),

    "gender": (
        "gender",
        "sex",
    ),

    "emirate": (
        "emirate",
        "issuing place",
        "place of issue",
    ),

    "license_no": (
        "license no",
        "licence no",
        "license number",
        "driving license",
        "dl no",
    ),

    "license_from_date": (
        "license from date",
        "issue date",
        "valid from",
    ),

    "license_to_date": (
        "license to date",
        "license expiry",
        "valid until",
    ),

    "chassis_no": (
        "chassis no",
        "vin",
        "vin no",
        "vehicle identification number",
    ),

    "registration_no": (
        "registration no",
        "reg no",
        "plate no",
    ),

    "registration_date": (
        "registration date",
        "reg date",
    ),

    "plate_code": (
        "plate code",
    ),

    "plate_source": (
        "plate source",
    ),

    "tcf_no": (
        "tcf no",
        "traffic file no",
    ),

    "model_year": (
        "model year",
        "year",
    ),

    "make_id": (
        "make id",
        "make",
        "manufacturer",
        "vehicle make",
    ),

    "model_id": (
        "model id",
        "model",
        "vehicle model",
    ),
}


DOCUMENT_TYPE_KEYWORDS = (
    ("emirates_id", ("emirates id", "identity card")),
    ("passport", ("passport",)),
    ("driving_license", ("driving license", "driving licence")),
    ("insurance_policy", ("insurance policy",)),
    ("invoice", ("invoice",)),
    ("vehicle_registration", ("vehicle registration", "mulkiya", "traffic file")),
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


INVALID_VALUES = {
    "select",
    "select plate code",
    "select plate source",
    "select ncd years",
    "select traffic tran type",
    "select engine capacity",
    "dd-mm-yyyy",
    "cancel",
    "submit",
    "yes",
    "no",
}


ARABIC_LABELS = {
    "جهة الترخيص",
    "اليابان",
    "رقم الرخصـة",
    "صنف المركبة",
    "رقم اللوحة",
    "تاريخ الانتهاء",
    "تاريخ الإصدار",
    "تاريخ التسجيل",
    "رقم الهيكل",
}

EMIRATE_KEYWORDS = {
    "dubai": "Dubai",
    "abu dhabi": "Abu Dhabi",
    "sharjah": "Sharjah",
    "ajman": "Ajman",
    "fujairah": "Fujairah",
    "ras al khaimah": "Ras Al Khaimah",
    "umm al quwain": "Umm Al Quwain",
}

INVALID_SELECTIONS = {
    "select model year",
    "select plate code",
    "select plate source",
    "select engine capacity",
    "select ncd years",
    "select traffic tran type",
    "dd-mm-yyyy",
    "submit",
    "cancel",
}

ARABIC_RE = re.compile(r"[\u0600-\u06FF]")

def infer_emirate(text: str) -> str | None:

    lower = text.lower()

    for keyword, emirate in EMIRATE_KEYWORDS.items():

        if keyword in lower:
            return emirate

    return None

def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()

def has_arabic(value: str) -> bool:
    return bool(ARABIC_RE.search(value))

def is_valid_value(field: str, value: str) -> bool:

    if not value:
        return False

    cleaned = normalize_space(value)

    if cleaned.lower() in INVALID_SELECTIONS:
        return False

    # reject arabic labels
    if field in {
        "model_id",
        "plate_code",
        "plate_source",
        "license_no",
    }:
        if has_arabic(cleaned):
            return False

    # MODEL YEAR
    if field == "model_year":

        if not re.fullmatch(r"(19|20)\d{2}", cleaned):
            return False

    # REGISTRATION DATE
    if field in {
        "registration_date",
        "license_from_date",
        "license_to_date",
    }:

        if parse_date(cleaned) is None:
            return False

    if field == "customer_name":
        label_words = {
            "name", "customer name", "full name", "holder name",
            "insured name", "customer", "holder", "insured",
        }
        if cleaned.lower() in label_words:
            return False
        if not re.search(r"[A-Za-z]", cleaned):
            return False

    return True

def parse_date(value: str) -> str | None:

    cleaned = normalize_space(value).replace(",", "")

    for fmt in DATE_FORMATS:

        try:
            return datetime.strptime(cleaned, fmt).strftime("%Y-%m-%d")

        except ValueError:
            continue

    match = re.search(
        r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b",
        cleaned,
    )

    if not match:
        return None

    day, month, year = match.groups()

    if len(year) == 2:
        year = f"20{year}" if int(year) < 30 else f"19{year}"

    try:
        return datetime(
            int(year),
            int(month),
            int(day),
        ).strftime("%Y-%m-%d")

    except ValueError:
        return None


def detect_document_type(text: str, fallback: str = "other") -> str:

    lowered = text.lower()

    for document_type, keywords in DOCUMENT_TYPE_KEYWORDS:

        if any(keyword in lowered for keyword in keywords):
            return document_type

    return fallback or "other"

def clean_extracted_data(data: dict) -> dict:

    remove_keys = []

    for key, value in data.items():

        if not value:
            remove_keys.append(key)
            continue

        value_str = str(value).strip()

        if value_str.lower() in INVALID_VALUES:
            remove_keys.append(key)
            continue

        if value_str in ARABIC_LABELS:
            remove_keys.append(key)
            continue

        if "select" in value_str.lower():
            remove_keys.append(key)
            continue

        if value_str.lower() == "dd-mm-yyyy":
            remove_keys.append(key)
            continue

        if value_str.lower().startswith("select"):
            remove_keys.append(key)
            continue

    for key in remove_keys:
        data.pop(key, None)

    return data


def clean_identifier(value: str, max_length: int = 40) -> str:
    return normalize_space(value).strip(" .,:;").upper()[:max_length]

def clean_registration_number(value: str) -> str | None:

    if not value:
        return None

    value = normalize_space(value).upper()

    # keep slash
    value = re.sub(
        r"[^A-Z0-9/]",
        "",
        value,
    )

    value = value.replace("I", "1")

    match = re.search(
        r"([A-Z]{1,3})/?(\d{4,10})",
        value,
    )

    if not match:
        return None

    prefix = match.group(1)
    number = match.group(2)

    return f"{prefix}/{number}"

def clean_model_name(value: str) -> str:

    value = normalize_space(value)

    # reject labels
    if re.search(
        r"\b(card|number|license|traffic|tcf|identity|emirates id)\b",
        value,
        re.IGNORECASE,
    ):
        return None

    remove_words = {
        "VEH",
        "VEHICLE",
        "CAR",
        "AUTO",
        "SUV",
    }

    cleaned_parts = []

    for part in value.split():

        if part.upper() not in remove_words:
            cleaned_parts.append(part)

    return " ".join(cleaned_parts).strip()

def extract_nationality(lines: list[str]) -> str | None:

    for i, line in enumerate(lines):

        if line.lower() == "nationality":

            if i + 1 < len(lines):

                nxt = normalize_space(lines[i + 1])

                if (
                    nxt
                    and nxt.lower() not in INVALID_VALUES
                    and not nxt.lower().startswith("emirates")
                ):
                    return nxt.title()

    return None

def is_valid_field_value(field: str, value: str) -> bool:

    if not value:
        return False

    cleaned = normalize_space(value)

    if cleaned.lower() in INVALID_VALUES:
        return False

    if cleaned in ARABIC_LABELS:
        return False

    if len(cleaned) < 2:
        return False
    
    if field == "registration_no":
        if re.search(r"[\u0600-\u06FF]", cleaned):
            return False
        if len(cleaned) < 4:
            return False

    if field == "customer_name":
        label_words = {
            "name", "customer name", "full name", "holder name",
            "insured name", "customer", "holder", "insured",
        }
        if cleaned.lower() in label_words:
            return False
        if not re.search(r"[A-Za-z]", cleaned):
            return False

    if field == "license_no":
        if re.search(r"[\u0600-\u06FF]", cleaned):
            return False
        if not re.search(r"\d", cleaned):
            return False
        
    
    if field == "model_id":
        cleaned = clean_model_name(cleaned)
        if not cleaned:
            return False
        if re.search(r"[\u0600-\u06FF]", cleaned):
            return False
        if cleaned.lower() in {
            "vehicle type",
            "body type",
            "model",
        }:
            return False
        
    if field in {"license_from_date","license_to_date","registration_date",}:
        if cleaned.lower() == "dd-mm-yyyy":
            return False
        if parse_date(cleaned) is None:
            return False

    if field == "model_year":
        if "select" in cleaned.lower():
            return False
        if not re.fullmatch(r"(19|20)\d{2}", cleaned):
            return False

    if field in {"plate_code", "plate_source"}:
        if "select" in cleaned.lower():
            return False
        
    if field == "registration_no":
        if not re.search(r"[A-Z0-9]", cleaned, re.IGNORECASE):
            return False

    return True


def normalize_field_value(field: str, value: str) -> str | None:

    value = normalize_space(value)

    if field.endswith("date") or field in {
        "date_of_birth",
        "id_expiry_date",
        "license_from_date",
        "license_to_date",
        "registration_date",
    }:
        return parse_date(value)

    if field == "emirates_id":

        digits = re.sub(r"\D", "", value)

        if len(digits) == 15 and digits.startswith("784"):

            return (
                f"{digits[:3]}-"
                f"{digits[3:7]}-"
                f"{digits[7:14]}-"
                f"{digits[14:]}"
            )

        return None

    if field == "chassis_no":

        match = re.search(
            r"\b[A-HJ-NPR-Z0-9]{17}\b",
            value,
            re.IGNORECASE,
        )

        return match.group(0).upper() if match else None

    if field == "registration_no":
        return clean_registration_number(value)

    if field in {
        "license_no",
        "plate_code",
        "tcf_no",
    }:
        return clean_identifier(value)

    return value


def extract_labeled_value(
    lines: list[str],
    aliases: tuple[str, ...],
    field_name: str,
) -> str | None:

    for index, line in enumerate(lines):

        lowered = line.lower()

        for alias in aliases:

            if alias not in lowered:
                continue

            # SAME LINE
            same_line = re.match(
                r"^.*?\b"
                + re.escape(alias)
                + r"\b\s*[:\-]?\s*(.+)$",
                line,
                re.IGNORECASE,
            )

            if same_line:

                value = normalize_space(
                    same_line.group(1)
                )

                if is_valid_value(field_name, value):
                    return value

            # ONLY NEXT LINE
            if index + 1 < len(lines):

                next_line = normalize_space(
                    lines[index + 1]
                )

                if is_valid_value(field_name, next_line):
                    return next_line

    return None


def extract_dates(text: str) -> list[str]:

    candidates = re.findall(
        r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"
        r"\d{4}[/-]\d{1,2}[/-]\d{1,2}|"
        r"\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}|"
        r"[A-Za-z]{3,9}\s+\d{1,2}\s+\d{4})\b",
        text,
    )

    parsed = []

    for candidate in candidates:

        value = parse_date(candidate)

        if value and value not in parsed:
            parsed.append(value)

    return parsed

def extract_license_dates(lines: list[str]) -> dict:

    data = {}

    for i, line in enumerate(lines):

        lower = normalize_space(line).lower()

        # LICENSE FROM DATE
        if re.search(
            r"(license|licence).*(from|issue|valid from)",
            lower,
            re.IGNORECASE,
        ):

            candidate = None

            # SAME LINE FIRST
            same = re.search(
                r"(\d{2}[/-]\d{2}[/-]\d{4})",
                line,
            )

            if same:
                candidate = same.group(1)

            # NEXT LINE
            elif i + 1 < len(lines):

                candidate = normalize_space(
                    lines[i + 1]
                )

            parsed = parse_date(candidate)

            if parsed:

                year = int(parsed[:4])

                # reject DOB years
                if year >= 2000:
                    data["license_from_date"] = parsed

        # LICENSE TO DATE
        if re.search(
            r"(license|licence).*(to|expiry|expire)",
            lower,
            re.IGNORECASE,
        ):

            candidate = None

            # SAME LINE FIRST
            same = re.search(
                r"(\d{2}[/-]\d{2}[/-]\d{4})",
                line,
            )

            if same:
                candidate = same.group(1)

            # NEXT LINE
            elif i + 1 < len(lines):

                candidate = normalize_space(
                    lines[i + 1]
                )

            parsed = parse_date(candidate)

            if parsed:

                year = int(parsed[:4])

                if year >= 2020:
                    data["license_to_date"] = parsed

    return data

def extract_license_and_registration_from_text(
    text: str,
) -> dict:

    data = {}

    if not text:
        return data

    #
    # LIMIT OCR TEXT
    #
    text = text[:4000]

    #
    # CLEAN LINES
    #
    lines = [
        normalize_space(line)
        for line in text.splitlines()[:120]
        if normalize_space(line)
    ]

    #
    # EXTRACT DATES
    #
    found_dates = []

    for line in lines:

        matches = re.findall(
            r"\d{2}[/-]\d{2}[/-]\d{4}",
            line,
        )

        for m in matches:

            parsed = parse_date(m)

            if not parsed:
                continue

            year = int(parsed[:4])

            #
            # skip DOB-like years
            #
            if year < 2005:
                continue

            if parsed not in found_dates:
                found_dates.append(parsed)

    #
    # LICENSE DATES
    #
    if len(found_dates) >= 1:
        data["license_from_date"] = found_dates[0]

    if len(found_dates) >= 2:
        data["license_to_date"] = found_dates[1]
            
    return data

def extract_uae_fields(text: str) -> dict:

    data = {}

    normalized = normalize_space(text)

    emirates = re.search(
        r"784[-\s]?\d{4}[-\s]?\d{7}[-\s]?\d",
        normalized,
        re.IGNORECASE,
    )

    if emirates:
        data["emirates_id"] = emirates.group(0)

    dob = re.search(
        r"(?:dob|date of birth)[^\d]*(\d{2}[/-]\d{2}[/-]\d{4})",
        normalized,
        re.IGNORECASE,
    )

    if dob:
        data["date_of_birth"] = parse_date(dob.group(1))

    expiry = re.search(
        r"(?:id-expiry date|id expiry date|expiry date|valid until)[^\d]*(\d{2}[/-]\d{2}[/-]\d{4})",
        normalized,
        re.IGNORECASE,
    )

    if expiry:
        data["id_expiry_date"] = parse_date(expiry.group(1))

    gender = re.search(
        r"\b(male|female)\b",
        normalized,
        re.IGNORECASE,
    )

    if gender:
        data["gender"] = gender.group(1).title()

    chassis = re.search(
        r"\b[A-HJ-NPR-Z0-9]{17}\b",
        normalized,
        re.IGNORECASE,
    )

    if chassis:
        data["chassis_no"] = chassis.group(0).upper()

    return data


def extract_vehicle_fields(lines: list[str]) -> dict:

    registration_no = None
    
    data = {}

    for i, line in enumerate(lines):

        line = normalize_space(line)

        # MODEL YEAR
        if line.lower() == "model year":

            if i + 1 < len(lines):

                year = normalize_space(lines[i + 1])

                if (
                    re.fullmatch(r"(19|20)\d{2}", year)
                    and "select" not in year.lower()
                ):
                    data["model_year"] = year

        # MAKE
        if line.lower() == "make id":

            if i + 1 < len(lines):

                make = normalize_space(lines[i + 1])

                if make.upper() in KNOWN_MANUFACTURERS:
                    data["make_id"] = make.upper()

        # MODEL
        if line.lower() == "model id":

            if i + 1 < len(lines):

                model = normalize_space(lines[i + 1])

                if (
                    model not in ARABIC_LABELS
                    and len(model) > 2
                ):
                    data["model_id"] = model

        # CHASSIS
        if "chassis" in line.lower():

            # SAME LINE
            same_line_match = re.search(
                r"\b([A-HJ-NPR-Z0-9]{17})\b",
                line,
                re.IGNORECASE,
            )

            if same_line_match:

                data["chassis_no"] = (
                    same_line_match.group(1).upper()
                )

            # NEXT LINE
            elif i + 1 < len(lines):

                vin = normalize_space(lines[i + 1])

                match = re.search(
                    r"\b([A-HJ-NPR-Z0-9]{17})\b",
                    vin,
                    re.IGNORECASE,
                )

                if match:

                    data["chassis_no"] = (
                        match.group(1).upper()
                    )

        # TCF NUMBER
        if re.search(
            r"\b(tcf|traffic file)\b",
            line,
            re.IGNORECASE,
        ):

            # SAME LINE
            same_line_match = re.search(
                r"(?:tcf\s*(?:no|number)?|traffic\s*file\s*(?:no|number)?)"
                r"\s*[:\-]?\s*([A-Z0-9\-]{5,25})",
                line,
                re.IGNORECASE,
            )

            if same_line_match:

                value = same_line_match.group(1).strip()

                if value.lower() not in {
                    "no",
                    "number",
                    "tcf",
                }:
                    data["tcf_no"] = value

            # NEXT LINE
            elif i + 1 < len(lines):

                next_line = normalize_space(
                    lines[i + 1]
                )

                if (
                    next_line
                    and next_line.lower() not in INVALID_VALUES
                    and not re.search(
                        r"(plate|source|model|year)",
                        next_line,
                        re.IGNORECASE,
                    )
                ):

                    next_match = re.search(
                        r"\b[A-Z0-9\-]{5,25}\b",
                        next_line,
                        re.IGNORECASE,
                    )

                    if next_match:

                        data["tcf_no"] = (
                            next_match.group(0)
                        )

        # REGISTRATION NUMBER
        if re.search(
            r"(registration no|reg no|plate no)",
            line,
            re.IGNORECASE,
        ):

            for j in range(i + 1, min(i + 8, len(lines))):

                raw = normalize_space(lines[j]).upper()

                # SKIP INVALID LINES
                if any(
                    x in raw
                    for x in [
                        "TCF",
                        "TRAFFIC",
                        "FILE",
                        "CHASSIS",
                        "ENGINE",
                        "PLATE SOURCE",
                        "SOURCE",
                    ]
                ):
                    continue

                cleaned = raw

                cleaned = cleaned.replace("I", "1")
                cleaned = cleaned.replace("O", "0")

                cleaned = re.sub(
                    r"UAE[-\s]*DE[-\s]*",
                    "",
                    cleaned,
                    flags=re.IGNORECASE,
                )


                compact = re.sub(
                    r"[^A-Z0-9]",
                    "",
                    cleaned,
                )


                match = re.fullmatch(
                    r"([A-Z])(\d{3,5})",
                    compact,
                )

                if match:

                    prefix = match.group(1)
                    number = match.group(2)

                    registration_no = f"{prefix}/{number}"

                    break

                reverse_match = re.fullmatch(
                    r"(\d{3,5})([A-Z])",
                    compact,
                )

                if reverse_match:

                    number = reverse_match.group(1)
                    prefix = reverse_match.group(2)

                    data["registration_no"] = (
                        f"{prefix}/{number}"
                    )

                    break

        # REGISTRATION DATE
        if re.search(
            r"(registration date|reg date)",
            line,
            re.IGNORECASE,
        ):

            candidate = None

            # SAME LINE
            same = re.search(
                r"(\d{2}[/-]\d{2}[/-]\d{4})",
                line,
            )

            if same:

                candidate = same.group(1)

            # NEXT LINE
            elif i + 1 < len(lines):

                candidate = normalize_space(
                    lines[i + 1]
                )

            parsed = parse_date(candidate)

            if parsed:

                data["registration_date"] = parsed

        # PLATE CODE
        if re.search(
            r"plate code",
            line,
            re.IGNORECASE,
        ):

            if i + 1 < len(lines):

                plate = normalize_space(
                    lines[i + 1]
                )

                if (
                    plate
                    and plate.lower() not in INVALID_VALUES
                ):

                    data["plate_code"] = plate.upper()

        # PLATE SOURCE
        if re.search(
            r"plate source",
            line,
            re.IGNORECASE,
        ):

            if i + 1 < len(lines):

                source = normalize_space(
                    lines[i + 1]
                )

                if (
                    source
                    and source.lower() not in INVALID_VALUES
                ):

                    data["plate_source"] = source.title()

    return data

def convert_to_iso(date_str):

    if not date_str:
        return None

    cleaned = normalize_space(date_str).replace(",", "")

    all_formats = (
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d %m %Y",
        "%d/%m/%y",
        "%d-%m-%y",
        "%d-%b-%Y",
        "%d-%b-%y",
        "%d %b %Y",
        "%d %B %Y",
        "%d-%B-%Y",
        "%b %d %Y",
        "%B %d %Y",
        "%Y-%m-%d",
        "%Y/%m/%d",
    )

    for fmt in all_formats:
        try:
            return datetime.strptime(cleaned, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    # Last resort: parse_date now returns YYYY-MM-DD directly
    iso = parse_date(date_str)
    if iso:
        return iso

    return date_str

from .mulkiya_parser import parse_mulkiya

def extract_mulkiya_fields(text: str) -> dict:

    try:
        result = parse_mulkiya(text)

        data = (
            result.get("data")
            or result.get("values")
            or {}
        )

        mapped = {}

        # FRONT SIDE
        ocr_registration = clean_registration_number(data.get("registration_no"))
        if ocr_registration:
            mapped["registration_no"] = ocr_registration
        mapped["registration_date"] = data.get("registration_date")
        mapped["plate_code"] = data.get("plate_code")
        mapped["plate_source"] = (
            data.get("plate_source")
            or data.get("place_of_issue")
        )
        mapped["emirate"] = mapped["plate_source"]
        tcf_value = (
            data.get("tcf_no")
            or data.get("traffic_file_no")
            or data.get("traffic_file_number")
            or data.get("tcf")
        )

        if tcf_value:

            tcf_value = normalize_space(str(tcf_value))

            match = re.search(
                r"\b[A-Z0-9\-]{5,25}\b",
                tcf_value,
                re.IGNORECASE,
            )

            if match:
                mapped["tcf_no"] = match.group(0)

        # BACK SIDE
        mapped["model_year"] = data.get("model_year")
        mapped["chassis_no"] = data.get("chassis_no")

        # MAKE + MODEL
        make_value = (
            data.get("make")
            or data.get("vehicle_make")
        )

        if make_value:
            make_value = normalize_space(make_value).upper()

        mapped["make_id"] = make_value

        model_value = (
            data.get("model")
            or data.get("vehicle_model")
        )

        if model_value:
            model_value = clean_model_name(model_value)

        mapped["model_id"] = model_value

        # REMOVE EMPTY VALUES
        cleaned = {}

        for key, value in mapped.items():

            if value not in (None, "", "Select"):
                cleaned[key] = value

        return cleaned

    except Exception as e:

        print("Mulkiya extraction error:", str(e))
        return {}

def looks_like_person_name(value: str) -> bool:

    if not value:
        return False

    value = normalize_space(value)

    # reject numbers
    if re.search(r"\d{4,}", value):
        return False

    # reject emirates id
    if re.fullmatch(r"784[-\d\s]+", value):
        return False

    # reject mostly numeric strings
    digits = len(re.findall(r"\d", value))
    letters = len(re.findall(r"[A-Za-z]", value))

    if digits > letters:
        return False

    # must contain alphabets
    if not re.search(r"[A-Za-z]", value):
        return False

    # minimum words
    words = value.split()

    if len(words) < 2:
        return False

    return True

def clean_customer_name(value: str) -> str | None:

    if not value:
        return None

    value = normalize_space(value)

    # reject common labels
    if re.search(
        r"\b(card|number|license|traffic|tcf|identity|emirates id)\b",
        value,
        re.IGNORECASE,
    ):
        return None

    # remove common trailing labels only
    value = re.sub(
        r"\b(NATIONALITY|DOB|DATE OF BIRTH|ISSUING PLACE|EXPIRY DATE|SEX)\b.*",
        "",
        value,
        flags=re.IGNORECASE,
    ).strip()

    # remove arabic chars
    value = re.sub(
        r"[\u0600-\u06FF]+",
        "",
        value,
    ).strip()

    # keep only alphabets + spaces
    value = re.sub(
        r"[^A-Za-z\s]",
        "",
        value,
    ).strip()

    value = normalize_space(value)

    # validation
    if len(value) < 3:
        return None
    
    if not looks_like_person_name(value):
        return None

    if not re.search(r"[A-Za-z]", value):
        return None

    invalid_names = {
        "name",
        "customer",
        "holder",
        "insured",
        "customer name",
        "full name",
        "card number",
        "card no",
        "number",
        "id number",
        "identity number",
        "license number",
        "traffic file number",
        "tcf number",
    }

    if value.lower() in invalid_names:
        return None

    return value.title()

from .emirates_id import parse_emirates_id

def extract_emirates_fields(text: str) -> dict:

    try:
        lower = text.lower()
        is_back = (
            "issuing place" in lower
            or "occupation" in lower
            or "employer" in lower
            or "family sponsor" in lower
        ) and "784" not in text

        doc_type = "emirates_id_back" if is_back else None
        result = parse_emirates_id(text, document_type=doc_type)

        data = result.get("data", {})

        mapped = {}

        # CUSTOMER NAME
        mapped["customer_name"] = clean_customer_name(data.get("name"))

        if not looks_like_person_name(
            mapped.get("customer_name", "")
        ):
            mapped["customer_name"] = None

        # EMIRATES ID
        mapped["emirates_id"] = (
            data.get("emirates_id_number")
        )

        # DOB
        mapped["date_of_birth"] = convert_to_iso(
            data.get("date_of_birth")
        )

        # NATIONALITY
        mapped["nationality"] = (
            data.get("nationality")
        )

        # ID EXPIRY
        mapped["id_expiry_date"] = convert_to_iso(
            data.get("expiry_date")
        )

        # GENDER
        gender = data.get("sex")

        if gender == "M":
            mapped["gender"] = "Male"

        elif gender == "F":
            mapped["gender"] = "Female"

        # EMIRATE / ISSUING PLACE
        mapped["emirate"] = (
            data.get("issuing_place")
        )

        if is_back and mapped.get("emirate"):
            mapped["plate_source"] = mapped["emirate"]

        # REMOVE EMPTY VALUES
        cleaned = {}

        for key, value in mapped.items():

            if value not in (
                None,
                "",
                "Select",
                "dd-mm-yyyy",
            ):
                cleaned[key] = value

        return cleaned

    except Exception as e:

        print(
            "Emirates parser error:",
            str(e)
        )

        return {}

from .driving_license import parse_driving_license
def extract_license_fields(text: str) -> dict:

    try:

        result = parse_driving_license(
            text=text,
            document_type="driving_license_front"
        )

        data = result.get("data", {})

        mapped = {}

        # LICENSE NUMBER
        mapped["license_no"] = (
            data.get("license_no")
        )

        # CUSTOMER NAME
        mapped["customer_name"] = clean_customer_name(
            data.get("name")
        )

        if not looks_like_person_name(
            mapped.get("customer_name", "")
        ):
            mapped["customer_name"] = None

        # NATIONALITY
        mapped["nationality"] = (
            data.get("nationality")
        )

        # DOB
        mapped["date_of_birth"] = convert_to_iso(
            data.get("date_of_birth")
        )

        # # LICENSE ISSUE DATE
        # mapped["license_from_date"] = (
        #     convert_to_iso(
        #         data.get("issue_date")
        #     )
        # )

        # # LICENSE EXPIRY DATE
        # mapped["license_to_date"] = (
        #     convert_to_iso(
        #         data.get("expiry_date")
        #     )
        # )

        # EMIRATE
        mapped["emirate"] = (
            data.get("place_of_issue")
        )

        # TRAFFIC CODE
        mapped["traffic_code"] = (
            data.get("traffic_code")
        )

        # CLEAN EMPTY VALUES
        cleaned = {}

        for key, value in mapped.items():

            if value not in (
                None,
                "",
                "Select",
                "dd-mm-yyyy",
            ):

                cleaned[key] = value

        return cleaned

    except Exception as e:

        print(
            "Driving license parser error:",
            str(e)
        )

        return {}


_EMIRATE_DROPDOWN_MAP = {
    "dubai": "DUBAI",
    "abu dhabi": "ABU DHABI",
    "sharjah": "SHARJAH.  U.A.E",
    "ajman": "AJMAN",
    "fujairah": "FUJAIRAH",
    "ras al khaimah": "RAS AL-KHAIMAH",
    "ras al-khaimah": "RAS AL-KHAIMAH",
    "rak": "RAS AL-KHAIMAH",
    "umm al quwain": "UMM AL-QUWAIN",
    "umm al-quwain": "UMM AL-QUWAIN",
    "uaq": "UMM AL-QUWAIN",
}


def normalize_emirate_for_dropdown(value: str) -> str | None:
    if not value:
        return None
    key = value.strip().lower()
    return _EMIRATE_DROPDOWN_MAP.get(key)


_PLATE_SOURCE_DROPDOWN_MAP = {
    "dubai": "DUBAI",
    "abu dhabi": "ABU DHABI",
    "al ain": "AL AIN",
    "sharjah": "SHARJAH",
    "ajman": "AJMAN",
    "umm al quwain": "UMM AL QUWAIN",
    "umm al-quwain": "UMM AL QUWAIN",
    "uaq": "UMM AL QUWAIN",
    "fujairah": "FUJAIRAH",
    "ras al khaimah": "RAS AL KHAIMAH",
    "ras al-khaimah": "RAS AL KHAIMAH",
    "rak": "RAS AL KHAIMAH",
}


def normalize_plate_source_for_dropdown(value: str) -> str | None:
    if not value:
        return None
    key = value.strip().lower()
    return _PLATE_SOURCE_DROPDOWN_MAP.get(key)


def extract_structured_fields(
    text: str,
    *,
    confidence: float | None = None,
    document_type_hint: str = "other",
) -> dict[str, Any]:

    normalized_text = normalize_space(text)

    lines = [
        normalize_space(line)
        for line in text.splitlines()
        if normalize_space(line)
    ]

    detected_type = detect_document_type(
        normalized_text,
        document_type_hint,
    )

    extracted: dict[str, Any] = {
        "document_type": detected_type,
    }

    # UAE COMMON FIELDS
    uae_fields = extract_uae_fields(normalized_text)

    extracted.update(uae_fields)

    # EMIRATES ID PARSER
    emirates_fields = extract_emirates_fields(text)

    # EMIRATES DATA
    for key, value in emirates_fields.items():

        if value not in (None, ""):

            # preserve valid existing customer name
            if (
                key == "customer_name"
                and extracted.get("customer_name")
                and looks_like_person_name(
                    extracted["customer_name"]
                )
            ):
                continue

            extracted[key] = value

    # DRIVING LICENSE PARSER
    license_fields = extract_license_fields(text)

    # LICENSE DATA
    for key, value in license_fields.items():

        if value not in (None, ""):

            # preserve valid existing customer name
            if (
                key == "customer_name"
                and extracted.get("customer_name")
                and looks_like_person_name(
                    extracted["customer_name"]
                )
            ):
                continue

            extracted[key] = value

    # VEHICLE FIELDS
    vehicle_fields = extract_vehicle_fields(lines)

    for key, value in vehicle_fields.items():

        if value not in (None, ""):

            extracted[key] = value


    # LICENSE + REGISTRATION OCR EXTRACTION
    ocr_fields = extract_license_and_registration_from_text(
        normalized_text
    )

    for key, value in ocr_fields.items():

        if not value:
            continue

        #
        # DO NOT OVERRIDE
        # VALID REGISTRATION NUMBER
        #
        if (
            key == "registration_no"
            and extracted.get("registration_no")
        ):
            continue

        #
        # prevent DOB overlap
        #
        if (
            key in {
                "license_from_date",
                "license_to_date",
            }
            and extracted.get("date_of_birth")
            and value == extracted["date_of_birth"]
        ):
            continue

        extracted[key] = value

    mulkiya_fields = extract_mulkiya_fields(text)

    for key, value in mulkiya_fields.items():
        if key == "registration_no":
            continue

        if (
            key == "chassis_no"
            and extracted.get("chassis_no")
        ):
            continue

        if value:
            extracted[key] = value

    nationality = extract_nationality(lines)
    if nationality:
        extracted["nationality"] = nationality
    emirate = infer_emirate(normalized_text)
    if emirate and "emirate" not in extracted:
        extracted["emirate"] = emirate

    # LABEL BASED EXTRACTION
    for field, aliases in FIELD_ALIASES.items():

        if field in extracted and extracted[field]:
            continue

        value = extract_labeled_value(
            lines,
            aliases,
            field,
        )

        if not value:
            continue

        normalized_value = normalize_field_value(field,value,)

        if field == "model_id" and normalized_value:
            normalized_value = clean_model_name(normalized_value)

        if normalized_value:
            extracted[field] = normalized_value

    # CUSTOMER NAME
    if (
        "customer_name" not in extracted
        or not extracted.get("customer_name")
    ):

        customer_name_match = re.search(
            r"(?:customer\s+name|holder\s+name|insured\s+name|full\s+name)"
            r"\s*[:\-]?\s*([A-Za-z][A-Za-z\s]{2,60})",
            normalized_text,
            re.IGNORECASE,
        )

        if customer_name_match:

            candidate = clean_customer_name(
                customer_name_match.group(1)
            )

            if (
                candidate
                and looks_like_person_name(candidate)
            ):
                extracted["customer_name"] = candidate

    # NATIONALITY
    nationality_match = re.search(
        r"(?:nationality)\s*([A-Za-z ]{3,30})",
        normalized_text,
        re.IGNORECASE,
    )

    if nationality_match:

        nationality = normalize_space(
                nationality_match.group(1)
        )

        if nationality.lower() not in INVALID_VALUES:

            extracted.setdefault(
                "nationality",
                nationality.title(),
            )

    # EMIRATE
    emirate_match = re.search(
        r"\b(dubai|abu dhabi|sharjah|ajman|ras al khaimah|rak|uaq|umm al quwain|fujairah)\b",
        normalized_text,
        re.IGNORECASE,
    )

    if emirate_match:
        extracted.setdefault("emirate", emirate_match.group(1).title())

    # REGISTRATION DATE
    if "registration_date" not in extracted:

        reg_date = re.search(
            r"(?:registration date|reg date)[^\d]*(\d{2}[/-]\d{2}[/-]\d{4})",
            normalized_text,
            re.IGNORECASE,
        )

        if reg_date:

            extracted["registration_date"] = parse_date(
                reg_date.group(1)
            )

    # CLEAN EMPTY DATES
    for field in [
        "license_from_date",
        "license_to_date",
        "registration_date",
    ]:

        if extracted.get(field) == "dd-mm-yyyy":
            extracted.pop(field)

    # PLATE CODE
    if "plate_code" not in extracted:

        plate_code_match = re.search(
            r"(?:plate code)\s*[:\-]?\s*([A-Z0-9]{1,10})",
            normalized_text,
            re.IGNORECASE,
        )

        if plate_code_match:

            plate_code = normalize_space(
                plate_code_match.group(1)
            )

            if plate_code.lower() not in INVALID_VALUES:
                extracted["plate_code"] = plate_code

    # PLATE SOURCE
    if "plate_source" not in extracted:

        plate_source_match = re.search(
            r"(?:plate source)\s*[:\-]?\s*([A-Z ]{2,30})",
            normalized_text,
            re.IGNORECASE,
        )

        if plate_source_match:

            source = normalize_space(
                plate_source_match.group(1)
            )

            if source.lower() not in INVALID_VALUES:
                extracted["plate_source"] = source.title()

    # VEHICLE MATCH
    vehicle_match = re.search(
        r"\b("
        + "|".join(KNOWN_MANUFACTURERS)
        + r")\s+([A-Z0-9\- ]{2,30})",
        normalized_text,
        re.IGNORECASE,
    )

    if vehicle_match:

        extracted.setdefault(
            "make_id",
            vehicle_match.group(1).upper(),
        )

        model = vehicle_match.group(2).strip()

        if model not in ARABIC_LABELS:

            extracted.setdefault(
                "model_id",
                model.upper(),
            )

    # ALL DATES
    dates = extract_dates(normalized_text)

    if dates:
        extracted.setdefault("dates_found", dates)

    # FINAL CUSTOMER NAME VALIDATION
    if "customer_name" in extracted:

        if not looks_like_person_name(
            extracted["customer_name"]
        ):
            extracted.pop("customer_name")

    # REMOVE DUPLICATE LICENSE DATES
    if (
        extracted.get("license_from_date")
        and extracted.get("license_to_date")
        and extracted["license_from_date"]
        == extracted["license_to_date"]
    ):
        extracted.pop("license_to_date", None)

    cleaned_output = {
        key: value
        for key, value in extracted.items()
        if value not in (None, "")
    }

    if "emirate" in cleaned_output:
        normalized = normalize_emirate_for_dropdown(cleaned_output["emirate"])
        if normalized:
            cleaned_output["emirate"] = normalized
        else:
            cleaned_output.pop("emirate")

    if "plate_source" in cleaned_output:
        normalized = normalize_plate_source_for_dropdown(cleaned_output["plate_source"])
        if normalized:
            cleaned_output["plate_source"] = normalized
        else:
            cleaned_output.pop("plate_source")


    return clean_extracted_data(cleaned_output)
import re
from datetime import datetime
from difflib import SequenceMatcher


# HELPERS
def normalize_text(text):

    if not text:
        return ""

    return re.sub(r"\s+", " ", str(text)).strip()

def clean_value(value):

    if value is None:
        return None

    value = str(value).strip()

    value = re.sub(r"\s+", " ", value)

    if not value:
        return None

    lower = value.lower()

    if lower in [
        "null",
        "none",
        "n/a",
        "na",
        "-"
    ]:
        return None

    if not any(c.isalnum() for c in value):
        return None

    return value.strip(" :-")

def similarity(a, b):

    return SequenceMatcher(
        None,
        (a or "").lower(),
        (b or "").lower()
    ).ratio()

def clean_name_field(value: str) -> str:
    if not value:
        return None

    # normalize spaces
    value = re.sub(r"\s+", " ", value).strip()

    # remove ONLY leading labels (safe)
    value = re.sub(r"^(name|الاسـم)\s+", "", value, flags=re.IGNORECASE)

    # remove repeated "Name Name ..." pattern
    value = re.sub(r"^(name\s+)+", "", value, flags=re.IGNORECASE)

    return value.strip()

# CONFIG

NOISE_PATTERNS = [
    r"دولة الإمارات العربية المتحدة.*",
    r"United Arab Emirates",
    r"رخصة قيادة",
    r"Driving License",
    r"Licensing Authority",
    r"سلطة الترخيص",
    r"RTA",
]

LABEL_PATTERNS = [
    r"License No\.?",
    r"رقم الرخصة",
    r"Name",
    r"الاسـم",
    r"Place of Issue",
    r"جهة الاصدار",
    r"Nationality",
    r"الجنسية",
    r"Date of Birth",
    r"تاريخ الميلاد",
    r"Issue Date",
    r"تاريخ الاصدار",
    r"Expiry Date",
    r"تاريخ الانتهاء",
]



# CLEAN TEXT

def clean_ocr_text(text: str) -> str:
    if not text:
        return ""

    # normalize spaces
    text = re.sub(r"\s+", " ", text)

    # remove noise lines
    for pattern in NOISE_PATTERNS:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)

    return text.strip()


# REMOVE LABELS BUT KEEP VALUES

def strip_labels(text: str) -> str:
    for label in LABEL_PATTERNS:
        text = re.sub(label, "", text, flags=re.IGNORECASE)
    return text


# EXTRACT KEY VALUE CLEANLY

def extract_value(raw_text: str, key: str):
    """
    Extract value after key label safely
    """

    pattern = rf"{key}\s*[:\-]?\s*(.+)"
    match = re.search(pattern, raw_text, re.IGNORECASE)

    if match:
        value = match.group(1)

        # stop at next label-like noise
        value = re.split(r"(License|Name|Place|Nationality|Date|Issue|Expiry|ال|تاريخ)", value)[0]

        return value.strip()

    return None

def fix_duplicate_label(field_value: str, label: str) -> str:
    if not field_value:
        return None

    value = field_value.strip()

    # normalize spaces
    value = re.sub(r"\s+", " ", value)

    label_clean = label.strip().lower()
    value_lower = value.lower()

    # CASE 1: "Name Name Fisal..."
    if value_lower.startswith(label_clean):
        value = re.sub(rf"^{re.escape(label)}\s*", "", value, flags=re.IGNORECASE)

    # CASE 2: repeated label pattern inside value
    value = re.sub(r"^(name\s+)+", "", value, flags=re.IGNORECASE)

    return value.strip()


# MAIN NORMALIZER

def normalize_license_data(raw_text: str):
    text = clean_ocr_text(raw_text)

    result = {}

    result["license_no"] = extract_value(text, "License No")
    result["name"] = extract_value(text, "Name")
    result["nationality"] = extract_value(text, "Nationality")
    result["date_of_birth"] = extract_value(text, "Date of Birth")
    result["issue_date"] = extract_value(text, "Issue Date")
    result["expiry_date"] = extract_value(text, "Expiry Date")
    result["place_of_issue"] = extract_value(text, "Place of Issue")

    # final cleanup pass
    for k, v in result.items():
        if v:
            v = re.sub(r"\s+", " ", v).strip()
            result[k] = v

    return result

# DATE NORMALIZATION

DATE_FORMATS = [

    "%d-%m-%Y",
    "%d/%m/%Y",
    "%d-%m-%y",
    "%d/%m/%y",

    "%d-%b-%Y",
    "%d/%b/%Y",

    "%d-%B-%Y",
    "%d/%B/%Y",

]


def normalize_date(date_value):

    if not date_value:
        return None

    cleaned = str(date_value).strip()
    cleaned = cleaned.replace(".", "-").replace("/", "-")
    cleaned = re.sub(r"\s+", "-", cleaned)

    # Title-case middle token if it looks like a month name (handles "27-SEP-2025" → "27-Sep-2025")
    parts = cleaned.split("-")
    if len(parts) == 3 and parts[1].isalpha():
        parts[1] = parts[1].capitalize()
        cleaned = "-".join(parts)

    formats = [
        "%d-%m-%Y",
        "%d-%m-%y",
        "%d-%b-%Y",
        "%d-%b-%y",
        "%d-%B-%Y",
        "%d-%B-%y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(cleaned, fmt).strftime("%d/%m/%Y")
        except ValueError:
            continue

    return None


# DATE EXTRACTION

DATE_PATTERN = (

    r"\b\d{2}[/-]\d{2}[/-]\d{2,4}\b"
    r"|"
    r"\b\d{2}[/-][A-Za-z]{3,9}[/-]\d{2,4}\b"

)


def extract_all_dates(text):

    matches = re.findall(
        DATE_PATTERN,
        text,
        flags=re.I
    )

    dates = []

    for match in matches:

        normalized = normalize_date(match)

        if normalized and normalized not in dates:
            dates.append(normalized)

    return dates


def extract_date_near_keywords(lines, keywords):

    for i, line in enumerate(lines):

        lower = line.lower()

        if any(k.lower() in lower for k in keywords):

            nearby = lines[
                max(0, i - 2):
                min(len(lines), i + 3)
            ]

            for item in nearby:

                match = re.search(
                    DATE_PATTERN,
                    item,
                    flags=re.I
                )

                if match:

                    normalized = normalize_date(
                        match.group()
                    )

                    if normalized:
                        return normalized

    return None


# EMIRATES NORMALIZATION

def normalize_emirate(text):

    if not text:
        return None

    text = text.lower()

    emirates = {

        "Dubai": [
            "dubai",
            "duba",
            "duabi"
        ],

        "Abu Dhabi": [
            "abu dhabi",
            "abudhabi",
            "abudabi"
        ],

        "Sharjah": [
            "sharjah",
            "sharja"
        ],

        "Ajman": [
            "ajman"
        ],

        "Ras Al Khaimah": [
            "rak",
            "ras al khaimah"
        ],

        "Fujairah": [
            "fujairah"
        ],

        "Umm Al Quwain": [
            "umm al quwain"
        ]
    }

    for emirate, aliases in emirates.items():

        for alias in aliases:

            if alias in text:
                return emirate

    return None


# LICENSE VALIDATION

def is_valid_license(candidate):

    if not candidate:
        return False

    candidate = candidate.strip().upper()

    if len(candidate) < 5:
        return False

    if len(candidate) > 20:
        return False

    blocked = [

        "LICENSE",
        "LICENCE",
        "DRIVING",
        "EMIRATES",
        "UNITED",
        "NATIONALITY",
        "TRAFFIC",
        "VEHICLE",
        "DUBAI"

    ]

    if candidate in blocked:
        return False

    if not re.search(r"\d", candidate):
        return False

    return True


# LICENSE NUMBER EXTRACTION

def extract_license_number(text, lines):

    upper_text = text.upper()

    patterns = [

        r"(?:LICENSE|LICENCE)\s*(?:NO|NUMBER|#)?\s*[:\-]?\s*([A-Z0-9\-]{5,20})",

        r"(?:DL|D\.L)\s*(?:NO|NUMBER)?\s*[:\-]?\s*([A-Z0-9\-]{5,20})"

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            upper_text,
            flags=re.I
        )

        if match:

            candidate = match.group(1)

            candidate = re.sub(
                r"[^A-Z0-9]",
                "",
                candidate
            )

            if is_valid_license(candidate):
                return candidate

    # FALLBACK

    for line in lines:

        candidates = re.findall(
            r"\b[A-Z0-9]{5,20}\b",
            line.upper()
        )

        for candidate in candidates:

            if is_valid_license(candidate):
                return candidate

    return None


# NAME EXTRACTION

def extract_name(text, lines):

    patterns = [

        r"Name\s*[:\-]?\s*([A-Za-z\s]+)",

        r"Holder\s*Name\s*[:\-]?\s*([A-Za-z\s]+)"

    ]

    blocked = [

        "United Arab Emirates",
        "Driving License",
        "Licence",
        "Traffic Code",
        "Traffic Code No",
        "Light Vehicle",
        "Automatic Gear",
        "Permitted Vehicles",
        "Vehicle"

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            flags=re.I
        )

        if match:

            value = clean_value(match.group(1))

            if value:

                value = re.sub(
                    r"[^A-Za-z\s]",
                    "",
                    value
                ).strip()

                words = value.split()

                if (

                    2 <= len(words) <= 6
                    and value.title() not in blocked

                ):

                    return value.title()

    # FALLBACK

    for line in lines:

        cleaned = re.sub(
            r"[^A-Za-z\s]",
            "",
            line
        ).strip()

        if not cleaned:
            continue

        words = cleaned.split()

        if not (2 <= len(words) <= 5):
            continue

        if cleaned.title() in blocked:
            continue

        lower = cleaned.lower()

        if any(k in lower for k in [

            "traffic",
            "vehicle",
            "license",
            "licence",
            "automatic"

        ]):

            continue

        return cleaned.title()

    return None


# NATIONALITY EXTRACTION

COUNTRIES = [

    "India",
    "Pakistan",
    "Nepal",
    "Bangladesh",
    "Sri Lanka",
    "Philippines",
    "Egypt",
    "Jordan",
    "Sudan",
    "Syria",
    "Oman",
    "Saudi Arabia",
    "United Arab Emirates"

]


def extract_nationality(text, lines):

    patterns = [

        r"Nationality\s*[:\-]?\s*([A-Za-z\s]+)",

        r"Nationaity\s*[:\-]?\s*([A-Za-z\s]+)"

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            flags=re.I
        )

        if match:

            value = clean_value(match.group(1))

            if value:

                value = re.sub(
                    r"[^A-Za-z\s]",
                    "",
                    value
                )

                return value.title()

    lower_text = text.lower()

    for country in COUNTRIES:

        if country.lower() in lower_text:
            return country

    return None


# PLACE EXTRACTION

def extract_place(text, lines):

    match = re.search(

        r"(?:Place\s*of\s*Issue|Issue\s*Place|Place)\s*[:\-]?\s*([A-Za-z\s]+)",

        text,

        flags=re.I

    )

    if match:

        emirate = normalize_emirate(
            match.group(1)
        )

        if emirate:
            return emirate

    # FALLBACK

    for line in lines:

        emirate = normalize_emirate(line)

        if emirate:
            return emirate

    return None


# TRAFFIC CODE EXTRACTION

def extract_traffic_code(text, lines):

    upper_text = text.upper()

    patterns = [

        r"TRAFFIC\s*CODE\s*(?:NO|NUMBER)?\.?\s*[:\-]?\s*([0-9]{5,15})",

        r"CODE\s*NO\.?\s*[:\-]?\s*([0-9]{5,15})",

        r"TRAFFIC\s*CODE[^\d]{0,20}(\d{5,15})",

    ]


    # DIRECT REGEX SEARCH

    for pattern in patterns:

        match = re.search(
            pattern,
            upper_text,
            flags=re.I | re.S
        )

        if match:

            value = match.group(1).strip()

            if re.fullmatch(r"\d{5,15}", value):
                return value


    # LINE SEARCH

    for i, line in enumerate(lines):

        lower = line.lower()

        if (

            "traffic code" in lower
            or "traffic code no" in lower
            or "code no" in lower
            or "الرمز المروري" in line

        ):

            # SAME LINE

            same_line_match = re.search(
                r"(\d{5,15})",
                line
            )

            if same_line_match:
                return same_line_match.group(1)

            # NEXT FEW LINES

            nearby_lines = lines[
                i : min(len(lines), i + 4)
            ]

            for nearby in nearby_lines:

                number_match = re.search(
                    r"\b\d{5,15}\b",
                    nearby
                )

                if number_match:
                    return number_match.group()


    # FINAL FALLBACK

    all_numbers = re.findall(
        r"\b\d{5,15}\b",
        text
    )

    if all_numbers:
        return all_numbers[0]

    return None


# VEHICLE TYPES

def extract_vehicle_types(text):

    vehicle_types = []

    lower = text.lower()

    mapping = {

        "light vehicle": "Light Vehicle",
        "motor cycle": "Motor Cycle",
        "automatic gear": "Automatic Gear",
        "heavy vehicle": "Heavy Vehicle"

    }

    for keyword, value in mapping.items():

        if keyword in lower:
            vehicle_types.append(value)

    return vehicle_types


# VALIDATION

def validate_driving_license(data, side="front"):

    errors = {}

    if side == "front":

        required_fields = [

            "license_no",
            "name",
            "date_of_birth",
            "issue_date",
            "expiry_date"

        ]

    else:

        required_fields = [
            "traffic_code"
        ]

    for field in required_fields:

        if not data.get(field):
            errors[field] = "Missing field"

    # DATE VALIDATION

    for field in [

        "date_of_birth",
        "issue_date",
        "expiry_date"

    ]:

        if data.get(field):

            try:

                datetime.strptime(
                    data[field],
                    "%d/%m/%Y"
                )

            except:

                errors[field] = "Invalid date"

    return errors



# CONFIDENCE

def confidence_score(value, field):

    if not value:
        return 0.0

    if field == "license_no":

        if re.fullmatch(r"[A-Z0-9]{5,20}", value):
            return 95.0

    if field == "name":

        if 2 <= len(value.split()) <= 6:
            return 90.0

    if field in [

        "date_of_birth",
        "issue_date",
        "expiry_date"

    ]:

        try:

            datetime.strptime(
                value,
                "%d/%m/%Y"
            )

            return 90.0

        except:
            return 50.0

    if field == "traffic_code":

        if re.fullmatch(r"\d{5,15}", value):
            return 95.0

    return 80.0


def calculate_confidence(data, validation_errors):

    confidence = {}

    for field, value in data.items():

        if field in validation_errors:

            confidence[field] = 0.0

        else:

            confidence[field] = confidence_score(
                value,
                field
            )

    overall = 0.0

    if confidence:

        overall = round(
            sum(confidence.values()) / len(confidence),
            1
        )

    confidence["overall_confidence"] = overall

    return confidence, overall


# AZURE OCR LINES

def get_lines_from_azure(azure_json):

    lines = []

    if not azure_json:
        return lines

    pages = azure_json.get("pages", [])

    for page in pages:

        for line in page.get("lines", []):

            if isinstance(line, dict):

                text = line.get("text", "")

            else:

                text = str(line)

            if text:
                lines.append(text.strip())

    return lines


# MAIN PARSER

def parse_driving_license(text,document_type="driving_license_front",key_values=None,tables=None,azure_json=None):

    lines = get_lines_from_azure(azure_json)

    if not lines:

        lines = [l.strip() for l in text.split("\n") if l.strip()]

    cleaned_text = normalize_text(text)

    lower_text = cleaned_text.lower()


    # AUTO SIDE DETECTION

    side = "front"

    back_keywords = [

        "traffic code",
        "traffic code no",
        "permitted vehicles",
        "vehicle types",
        "light vehicle",
        "automatic gear"

    ]

    if ("back" in document_type.lower()or any(k in lower_text for k in back_keywords)):
        side = "back"


    # BACK SIDE

    if side == "back":

        data = {
            "traffic_code": extract_traffic_code(cleaned_text,lines),
            "vehicle_types": extract_vehicle_types(cleaned_text)
        }

        validation_errors = validate_driving_license(data,side="back")

        confidence, overall_confidence = calculate_confidence(data,validation_errors)

        return {

            "document_type": "driving_license",

            "side": "back",

            "driving_license_side": "back",

            "data": data,

            "validation_errors": validation_errors,

            "confidence": confidence,

            "confidence_score": overall_confidence
        }


    # FRONT SIDE
    extracted_name = clean_name_field(extract_name(cleaned_text, lines))

    invalid_names = [

        "Traffic Code No",
        "Traffic Code",
        "Driving License",
        "Licence",
        "Vehicle",
        "Light Vehicle",
        "Automatic Gear"

    ]

    if extracted_name in invalid_names:
        extracted_name = None

    data = {

        "license_no": extract_license_number(cleaned_text,lines),

        "name": extracted_name,

        "nationality": extract_nationality(cleaned_text,lines),

        "date_of_birth": None,

        "issue_date": None,

        "expiry_date": None,

        "place_of_issue": extract_place(cleaned_text,lines)
    }


    # DATE EXTRACTION

    data["date_of_birth"] = extract_date_near_keywords(
        lines, ["birth", "dob", "date of birth", "تاريخ الميلاد"]
    )
    data["issue_date"] = extract_date_near_keywords(
        lines, ["issue date", "issue", "issued", "تاريخ الاصدار"]
    )
    data["expiry_date"] = extract_date_near_keywords(
        lines, ["expiry", "expiry date", "exp", "تاريخ الانتهاء"]
    )

    # fallback: if still missing, use positional order as last resort
    if not data["date_of_birth"] or not data["issue_date"] or not data["expiry_date"]:
        dates = extract_all_dates(cleaned_text)
        if len(dates) >= 3:
            data["date_of_birth"] = data["date_of_birth"] or dates[0]
            data["issue_date"] = data["issue_date"] or dates[1]
            data["expiry_date"] = data["expiry_date"] or dates[2]


    # VALIDATION
    validation_errors = validate_driving_license(data,side="front")

    confidence, overall_confidence = calculate_confidence(data,validation_errors)


    return {

        "document_type": "driving_license",

        "side": "front",

        "driving_license_side": "front",

        "data": data,

        "validation_errors": validation_errors,

        "confidence": confidence,

        "confidence_score": overall_confidence
    }
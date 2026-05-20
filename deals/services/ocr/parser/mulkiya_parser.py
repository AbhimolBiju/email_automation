import re
from datetime import datetime

from apps.ocr.nationality import extract_nationality_from_ocr


def normalize_date(date_value):
    if not date_value:
        return None

    cleaned = date_value.strip().upper()

    #normalize separators
    cleaned = re.sub(r"[.\s]+", "-", cleaned)
    cleaned = re.sub(r"/", "-", cleaned)

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
            return datetime.strptime(cleaned, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    return cleaned


def _normalize_token_for_match(text):
    token = (text or "").lower()
    token = re.sub(r"[^a-z]", "", token)
    return token


def normalize_emirate(text):
    if not text:
        return None

    # OCR-tolerant aliases and frequent misspellings.
    emirate_aliases = {
        "Dubai": [
            "dubai", "duba", "duabi", "dubi", "dbai", "dbi", "dubal", "دبي",
        ],
        "Abu Dhabi": [
            "abudhabi", "abu dhabi", "abudabi", "abudhbi", "ابوظبي",
        ],
        "Sharjah": [
            "sharjah", "sharja", "sharja", "شارقة", "الشارقة",
        ],
        "Ajman": [
            "ajman", "ajmaan", "عجمان",
        ],
        "Ras Al Khaimah": [
            "rasalkhaimah", "ras al khaimah", "ras al khaima", "rak", "راسالخيمة", "رأسالخيمة",
        ],
        "Fujairah": [
            "fujairah", "fujaira", "fujeirah", "الفجيرة",
        ],
        "Umm Al Quwain": [
            "ummalquwain", "umm al quwain", "umalquwain", "امالقيوين", "أمالقيوين",
        ],
    }

    raw_lower = text.lower()
    normalized = _normalize_token_for_match(text)

    for emirate, aliases in emirate_aliases.items():
        for alias in aliases:
            alias_norm = _normalize_token_for_match(alias)
            if alias.lower() in raw_lower or (alias_norm and alias_norm in normalized):
                return emirate
    return None


def _extract_dates_from_line(line):
    if not line:
        return []

    patterns = [
        r"\b\d{2}[/-]\d{2}[/-]\d{4}\b",
        r"\b\d{2}[.]\d{2}[.]\d{4}\b",
    ]
    found = []
    for pattern in patterns:
        found.extend(re.findall(pattern, line))
    return found


#new code added 
DATE_PATTERN = (
    r"\b\d{2}[/-]\d{2}[/-]\d{2,4}\b"
    r"|"
    r"\b\d{2}[-/\s][A-Za-z]{3,9}[-/\s]\d{2,4}\b"
)


def extract_date_near_keywords(lines, keywords, reject_keywords=None):
    reject_keywords = reject_keywords or []

    for i, line in enumerate(lines):
        line_lower = line.lower()

        if any(keyword in line_lower for keyword in keywords):
            nearby = lines[max(0, i - 3): min(len(lines), i + 4)]

            for item in nearby:
                item_lower = item.lower()

                if any(reject in item_lower for reject in reject_keywords):
                    continue

                match = re.search(DATE_PATTERN, item, re.IGNORECASE)
                if match:
                    return normalize_date(match.group())

    return None


def extract_registration_date(lines):
    if not lines:
        return None

    reg_label_patterns = [
        r"\breg(?:istration)?\.?\s*(?:date|dt)?\b",
        r"\bdate\s*of\s*registration\b",
        r"\bregistration\b",
    ]
    exp_negative_pattern = r"\b(exp|expiry|ins|insurance)\b"
    best = None
    best_score = -1

    for i, line in enumerate(lines):
        line_lower = line.lower()
        if any(re.search(pattern, line_lower) for pattern in reg_label_patterns):
            # Keep registration date tied to registration-region only.
            for j in range(max(0, i - 2), min(len(lines), i + 4)):
                candidate_line = lines[j]
                candidate_lower = candidate_line.lower()
                if re.search(exp_negative_pattern, candidate_lower):
                    continue
                for raw_date in _extract_dates_from_line(candidate_line):
                    normalized = normalize_date(raw_date)
                    if not normalized:
                        continue
                    # Prefer same-line then nearest lines.
                    score = 20 - abs(j - i) * 4
                    if j == i:
                        score += 8
                    if "reg" in candidate_lower or "registration" in candidate_lower:
                        score += 4
                    if score > best_score:
                        best = normalized
                        best_score = score
    return best


def extract_plate_source(lines):
    if not lines:
        return None

    label_patterns = [
        r"\bplate\s*source\b",
        r"\bplace\s*source\b",
        r"\bplace\s*of\s*issue\b",
        r"\bemirate\b",
        r"\bsource\b",
    ]

    best_emirate = None
    best_score = -1
    search_radius = 3

    for i, line in enumerate(lines):
        line_lower = line.lower()
        if any(re.search(p, line_lower) for p in label_patterns):
            for j in range(max(0, i - search_radius), min(len(lines), i + search_radius + 1)):
                candidate_line = lines[j]
                emirate = normalize_emirate(candidate_line)
                if not emirate:
                    continue
                # Strongly prefer values closest to source/emirate labels.
                score = 30 - abs(j - i) * 5
                if j == i:
                    score += 10
                if ":" in candidate_line:
                    score += 2
                if score > best_score:
                    best_emirate = emirate
                    best_score = score

    # Last resort only if no label-near candidate exists.
    if not best_emirate:
        for line in lines:
            emirate = normalize_emirate(line)
            if emirate:
                best_emirate = emirate
                break

    return best_emirate

def extract_front_plate_details(lines):
    for i, line in enumerate(lines):
        if "traffic plate" in line.lower():
            nearby = lines[max(0, i - 6): i + 2]

            plate_number = None
            plate_code = None

            for item in nearby:
                item = item.strip()

                if re.fullmatch(r"\d{3,6}", item):
                    plate_number = item

                if re.fullmatch(r"[A-Z]{1,3}", item):
                    if item not in ["UAE", "RTA"]:
                        plate_code = item

            return plate_code, plate_number

    return None, None

def extract_front_registration_date_fallback(lines):
    for i, line in enumerate(lines):
        if "تاريخ الترخيص" in line or "reg" in line.lower():
            nearby = lines[max(0, i - 2): min(len(lines), i + 4)]

            for item in nearby:
                if "exp" in item.lower() or "ins" in item.lower():
                    continue

                m = re.search(r"\b\d{2}[/-]\d{2}[/-]\d{4}\b", item)
                if m:
                    return normalize_date(m.group())

    return None


def extract_owner(lines):
    if not lines:
        return None

    owner_label_patterns = [
        r"\btraffic\s*file\s*owner\b",
        r"\bowner\b",
        r"\bname\b",
        r"المالك",
    ]

    blocked_terms = [
        "owner", "name", "traffic", "file", "vehicle", "license", "licence", "registration",
        "reg", "exp", "expiry", "insurance", "policy", "plate", "source", "issue", "emirate",
        "model", "chassis", "engine", "nationality", "private", "united arab emirates", "uae",
    ]

    def is_valid_owner_candidate(value):
        if not value:
            return False
        candidate = re.sub(r"\s+", " ", value).strip()
        candidate_lower = candidate.lower()
        if len(candidate.split()) < 2 or len(candidate.split()) > 6:
            return False
        if re.search(r"\d", candidate):
            return False
        if re.search(r"\b\d{2}[/-]\d{2}[/-]\d{4}\b", candidate):
            return False
        if not re.match(r"^[A-Za-z\s\-'.]+$", candidate):
            return False
        if any(term in candidate_lower for term in blocked_terms):
            return False
        if normalize_emirate(candidate):
            return False
        return True

    best_candidate = None
    best_score = -1

    for i, line in enumerate(lines):
        line_lower = line.lower()
        if any(re.search(p, line_lower) for p in owner_label_patterns):
            for j in range(max(0, i - 3), min(len(lines), i + 5)):
                candidate = lines[j]
                if not is_valid_owner_candidate(candidate):
                    continue
                score = 20 - abs(j - i) * 4
                if j > i:
                    score += 2
                if ":" in line and j == i:
                    score += 5
                if score > best_score:
                    best_candidate = candidate
                    best_score = score

    if best_candidate:
        return re.sub(r"\s+", " ", best_candidate).strip().title()
    return None

def extract_front_owner_fallback(lines):
    for line in lines:
        candidate = re.sub(r"\s+", " ", line).strip()

        if re.search(r"\d", candidate):
            continue

        if not re.fullmatch(r"[A-Z][A-Z\s.'-]{5,}", candidate):
            continue

        blocked = [
            "UNITED ARAB EMIRATES",
            "VEHICLE LICENSE",
            "TRAFFIC PLATE",
            "NATIONALITY",
            "PRIVATE",
        ]

        if candidate.upper() in blocked:
            continue

        if 2 <= len(candidate.split()) <= 6:
            return candidate.title()

    return None


def get_value_before_label(lines, label):
    for i, line in enumerate(lines):
        if label.lower() in line.lower():
            if i > 0:
                return lines[i - 1].strip()
    return None


def get_value_after_label(lines, label):
    for i, line in enumerate(lines):
        if label.lower() in line.lower() and i + 1 < len(lines):
            return lines[i + 1].strip()
    return None


def clean_code(value):
    if not value:
        return None
    return re.sub(r"[^A-Za-z0-9]", "", value).upper()

def find_code_near_label(lines, label, min_len=6, max_len=20):
    for i, line in enumerate(lines):
        if label.lower() in line.lower():

            # check more lines below the label
            for j in range(i + 1, min(i + 15, len(lines))):
                candidate = clean_code(lines[j])

                if (
                    candidate
                    and min_len <= len(candidate) <= max_len
                    and re.search(r"\d", candidate)
                    and not candidate.isdigit()
                    and candidate not in ["UAE", "RTA"]
                    and not candidate.startswith(("WWW", "STMT"))
                ):
                    return candidate
            # check more lines above the label
            for j in range(i - 1, max(i - 15, -1), -1):
                candidate = clean_code(lines[j])

                if (
                    candidate
                    and min_len <= len(candidate) <= max_len
                    and re.search(r"\d", candidate)
                    and not candidate.isdigit()
                    and candidate not in ["UAE", "RTA"]
                    and not candidate.startswith(("WWW", "STMT"))
                ):
                    return candidate

    return None

FRONT_REQUIRED_FIELDS = [
    "registration_no",
    "registration_date",
    "plate_code",
    "place_of_issue",
    "plate_number",
    "tcf_no",
    "owner",
]

def validate_mulkiya_front(data):
    errors = {}

    required_fields = [
        "registration_no",
        "registration_date",
        "plate_code",
        "place_of_issue",
        "plate_number",
        "tcf_no",
        "owner",
    ]

    for field in required_fields:
        if not data.get(field):
            errors[field] = "Missing field"

    if data.get("registration_no") and not re.fullmatch(r"\d{3,6}", data["registration_no"]):
        errors["registration_no"] = "Invalid registration number format"

    if data.get("registration_date") and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", data["registration_date"]):
        errors["registration_date"] = "Invalid date format"

    if data.get("plate_number") and not re.fullmatch(r"\d{3,6}", data["plate_number"]):
        errors["plate_number"] = "Invalid plate number format"

    return errors


def calculate_mulkiya_front_confidence(data, validation_errors):
    fields = [
        "registration_no",
        "registration_date",
        "plate_code",
        "place_of_issue",
        "plate_number",
        "tcf_no",
        "owner",
    ]

    confidence = {}

    for field in fields:
        confidence[field] = 90.0 if data.get(field) and field not in validation_errors else 0.0

    confidence["overall_confidence"] = round(
        sum(confidence.values()) / len(fields), 2
    )

    return confidence

def validate_mulkiya_back(data):
    errors = {}

    required_fields = [
        "model_year",
        "origin",
        "number_of_passengers",
        "vehicle_type",
        "chassis_no",
    ]

    for field in required_fields:
        if not data.get(field):
            errors[field] = "Missing field"

    if data.get("model_year") and not re.fullmatch(r"(19|20)\d{2}", data["model_year"]):
        errors["model_year"] = "Invalid model year format"

    if data.get("number_of_passengers") and not re.fullmatch(r"\d{1,2}", data["number_of_passengers"]):
        errors["number_of_passengers"] = "Invalid passenger count format"

    if data.get("chassis_no") and not re.fullmatch(r"[A-Z0-9]{15,18}", data["chassis_no"]):
        errors["chassis_no"] = "Invalid chassis number format"

    if data.get("engine_no") and not re.fullmatch(r"[A-Z0-9]{5,18}", data["engine_no"]):
        errors["engine_no"] = "Invalid engine number format"

    return errors


def calculate_mulkiya_back_confidence(data, validation_errors):
    fields = [
        "model_year",
        "origin",
        "number_of_passengers",
        "vehicle_type",
        "chassis_no",
    ]

    confidence = {}

    for field in fields:
        confidence[field] = 90.0 if data.get(field) and field not in validation_errors else 0.0

    if data.get("engine_no") and "engine_no" not in validation_errors:
        confidence["engine_no"] = 90.0
    else:
        confidence["engine_no"] = 0.0

    confidence["overall_confidence"] = round(
        sum(confidence[field] for field in fields) / len(fields),
        2
    )

    return confidence


def parse_mulkiya(text, key_values=None, tables=None, document_type=None):

    data = {"document_type":"mulkiya"}
    cleaned = re.sub(r"[ \t]+", " ", text)
    cleaned = re.sub(r"\n+", "\n", cleaned).strip()
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    full_text = "\n".join(lines)
    compact_text = " ".join(lines)


    key_values=key_values or {}

    def normalize_key(text):
        text = (text or "").lower()
        text = re.sub(r"[^a-z0-9]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()


    def get_kv_value(possible_keys):
        normalized_possible = [normalize_key(k) for k in possible_keys]

        for key, value in key_values.items():
            nk = normalize_key(key)

            for pk in normalized_possible:
                if pk in nk or nk in pk:
                    return value.strip() if value else None

        return None

    
    # ---------------- FRONT SIDE ---------------- (key value pair)

    # 🔹 Plate Number
    plate_value = get_kv_value([
        "traffic plate no", "plate no", "plate number","رقم اللوحة"
        ])

    if plate_value:
        m = re.search(r"\b([A-Z0-9]{1,3})\s*/\s*(\d{3,6})\b", plate_value.upper())
        if m:
            data["plate_code"] = m.group(1)
            data["plate_number"] = m.group(2)
            data["registration_no"] = f"{m.group(1)}/{m.group(2)}"


    # 🔹 Place of Issue
    place_value = get_kv_value([
        "place of issue", "plate source", "emirate","جهة الترخيص"
        ])

    if place_value:
        place = normalize_emirate(place_value)
        if place:
            data["place_of_issue"] = place
            data["plate_source"] = place

    # 🔹 TCF No
    tcf_value = get_kv_value([
        "t c no", "tc no", "tcf no", "t.c. no", "traffic code", "traffic file no", "tcf"
        ])

    if tcf_value:
        m = re.search(r"\d{6,10}", tcf_value)
        if m:
            data["tcf_no"] = m.group()


    # 🔹 Owner
    owner_value = get_kv_value([
        "owner", "traffic file owner","المالك"
        ])

    if owner_value:
        owner_clean = re.sub(r"[^A-Za-z\s.'-]", "", owner_value)
        owner_clean = re.sub(r"\s+", " ", owner_clean).strip()

        if len(owner_clean.split()) >= 2:
            data["owner"] = owner_clean.title()
    
    # 🔹 Nationality — Nationality / الجنسية label (same patterns as Emirates ID)
    nationality_value = extract_nationality_from_ocr(
        full_text,
        existing_fields=key_values,
    )
    if nationality_value:
        data["nationality"] = nationality_value


    # 🔹 Registration Date
    reg_date_value = get_kv_value([
        "reg date", "registration date","تاريخ الترخيص"
        ])

    if reg_date_value:
        m = re.search(r"\d{2}[/-]\d{2}[/-]\d{4}", reg_date_value)
        if m:
            data["registration_date"] = normalize_date(m.group())


    # 🔹 Expiry Date
    exp_date_value = get_kv_value([
        "exp date", "expiry date"
        ])

    if exp_date_value:
        m = re.search(r"\d{2}[/-]\d{2}[/-]\d{4}", exp_date_value)
        if m:
            data["registration_expiry_date"] = normalize_date(m.group())


    # 🔹 Insurance Expiry
    ins_value = get_kv_value([
        "ins exp", "insurance"
        ])

    if ins_value:
        m = re.search(r"\d{2}[/-]\d{2}[/-]\d{4}", ins_value)
        if m:
            data["insurance_expiry_date"] = normalize_date(m.group())


    # 🔹 Policy No
    policy_value = get_kv_value([
        "policy no"
        ])

    if policy_value:
        data["policy_no"] = policy_value   



    # ---------------- FRONT SIDE ----------------(line by line fallback)

    # Registration / plate number: U / 19033

    if "registration_no" not in data or "plate_number" not in data:
        for plate_match in re.finditer(r"\b([A-Z]{1,3})\s*/\s*(\d{3,6})\b", compact_text.upper()):
            plate_code = plate_match.group(1)
            plate_number = plate_match.group(2)
            if plate_code.isdigit():
                continue
            if re.fullmatch(r"\d{2}", plate_code) and len(plate_number) == 4:
                continue
            data["plate_code"] = plate_code
            data["plate_number"] = plate_number
            data["registration_no"] = plate_number
            break
    

    # NEW FALLBACK: handles plate formats like 68297 W 68297
    if "registration_no" not in data or "plate_number" not in data:
        plate_code = None
        plate_number = None

        for i, line in enumerate(lines):
            if "traffic plate" in line.lower():
                nearby = lines[max(0, i - 2): min(len(lines), i + 8)]

                numbers = []
                codes = []

                for item in nearby:
                    item_clean = item.strip().upper()

                    if re.fullmatch(r"\d{3,6}", item_clean):
                        numbers.append(item_clean)

                    if re.fullmatch(r"[A-Z]{1,3}", item_clean) and item_clean not in ["UAE", "RTA"]:
                        codes.append(item_clean)
                if numbers:
                    plate_number = numbers[0]

                if codes:
                    plate_code = codes[0]

                if plate_number and plate_code:
                    data["plate_number"] = plate_number
                    data["plate_code"] = plate_code
                    data["registration_no"] = plate_number

                break


    # Traffic code / TCF No

    if "tcf_no" not in data:
        tc_match = re.search(r"\b(\d{8,10})\b", compact_text)

        if tc_match:
            data["tcf_no"] = tc_match.group(1)
        else:
            # strict fallback: only match lines that actually contain tcf/traffic code labels
            for i, line in enumerate(lines):
                line_lower = line.lower()
                if (
                    "tcf" in line_lower
                    or "t c no" in line_lower
                    or "traffic code" in line_lower
                    or "traffic file no" in line_lower
                ):
                    for j in range(i, min(i + 4, len(lines))):
                        m = re.search(r"\b(\d{6,10})\b", lines[j])
                        if m:
                            data["tcf_no"] = m.group(1)
                            break
                if "tcf_no" in data:
                    break


    # Place of issue / plate source: use label-near extraction, then normalize.

    # Step 1: try structured extraction
    if "place_of_issue" not in data:
        plate_source = extract_plate_source(lines)
        if plate_source:
            data["plate_source"] = plate_source
            data["place_of_issue"] = plate_source

    # Step 2: scan near Place of Issue / جهة label
    if "place_of_issue" not in data:
        for i, line in enumerate(lines):
            if "place" in line.lower() or "جهة" in line:
                nearby = lines[max(0, i - 5): min(len(lines), i + 6)]

                for item in nearby:
                    emirate = normalize_emirate(item)
                    if emirate:
                        data["place_of_issue"] = emirate
                        data["plate_source"] = emirate
                        break

            if "place_of_issue" in data:
                break

    # Step 3: scan all lines as final fallback
    if "place_of_issue" not in data:
        for line in lines:
            emirate = normalize_emirate(line)
            if emirate:
                data["place_of_issue"] = emirate
                data["plate_source"] = emirate
                break

    # Owner: avoid labels, dates, numbers and non-name metadata.

    if "owner" not in data:
        def valid_owner(value):
            return (
                value
                and re.match(r"^[A-Za-z ]+$", value)
                and len(value.split()) >= 2
                and value.lower() not in ["india", "owner", "nationality", "private"]
                )
    
        owner = None

        for i, line in enumerate(lines):
            if "owner" in line.lower() or "المالك" in line:
                if i + 1 < len(lines) and valid_owner(lines[i + 1]):
                    owner = lines[i + 1]

                elif i > 0 and valid_owner(lines[i - 1]):
                    owner = lines[i - 1]
                    break

        # fallback: scan full text for ALL CAPS names
        if not owner:
            for line in lines:
                if re.match(r"^[A-Z ]{6,}$", line.strip()) and valid_owner(line):
                    owner = line
                    break
        if owner:
            data["owner"] = owner.title()


    # Dates

    registration_expiry_date = extract_date_near_keywords(
        lines,
        keywords=["exp. date", "exp date", "expiry date"],
        reject_keywords=["ins"]
        )

    registration_date = extract_date_near_keywords(
        lines,
        keywords=["reg. date", "reg date", "registration date", "تاريخ الترخيص"]
        )

    insurance_expiry_date = extract_date_near_keywords(
        lines,
        keywords=["ins. exp", "ins exp", "insurance"]
        )

    if "registration_expiry_date" not in data and registration_expiry_date:
        data["registration_expiry_date"] = registration_expiry_date

    if "registration_date" not in data and registration_date:
        data["registration_date"] = registration_date

    if "insurance_expiry_date" not in data and insurance_expiry_date:
        data["insurance_expiry_date"] = insurance_expiry_date


    # Policy No
    if "policy_no" not in data:
        policy_match = re.search(r"Policy\s*No\.?\s*([A-Z0-9]+)", cleaned, re.IGNORECASE)
        if not policy_match:
            policy_match = re.search(r"\b\d{3,}[A-Z]{1,5}\d{3,}\b", cleaned)
        if policy_match:
            data["policy_no"] = policy_match.group(1) if policy_match.lastindex else policy_match.group(0)
    

# =========================
# MULKIYA BACK FIELDS - WHOLE TEXT PATTERN BASED
# =========================
    # Model year
    if "model_year" not in data:
        for i, line in enumerate(lines):
            if "model" in line.lower() or "سنة الصنع" in line:
                nearby = lines[max(0, i - 5): min(len(lines), i + 2)]
                for candidate in nearby:
                    year_match = re.search(r"\b(19|20)\d{2}\b", candidate)
                    if year_match:
                        data["model_year"] = year_match.group(0)
                        break
            if "model_year" in data:
                break


    # Origin

    if "origin" not in data:
        for i, line in enumerate(lines):
            if "origin" in line.lower() or "بلد الصنع" in line:
                nearby = lines[max(0, i - 5): min(len(lines), i + 2)]

                for candidate in nearby:
                    candidate = candidate.strip()

                    if (
                        re.fullmatch(r"[A-Za-z ]{3,}", candidate)
                        and candidate.lower() not in [
                            "origin", "model", "vehicle", "information",
                            "rta", "uae", "licensing", "authority"]):
                        data["origin"] = candidate.title()
                        break
            if "origin" in data:
                break

     # Number of passengers
    for i, line in enumerate(lines):
        if "pass" in line.lower() or "ركاب" in line:
            for j in range(max(0, i - 3), min(i + 4, len(lines))):
                m = re.search(r"\b\d{1,2}\b", lines[j])
                if m and 1 <= int(m.group(0)) <= 99:
                    data["number_of_passengers"] = m.group(0)
                    break
            if "number_of_passengers" in data:
                break
        # fallback: find passenger count anywhere
        if "number_of_passengers" not in data:
            for i, line in enumerate(lines):
                candidate = line.strip()

                # Must be a number
                if not re.fullmatch(r"\d{1,3}", candidate):
                    continue

                value = int(candidate)

                # Reject impossible values
                if value <= 0 or value > 60:
                    continue

                context = " ".join(lines[max(0, i-2):min(len(lines), i+3)]).lower()

                # Reject if clearly not passengers
                if any(x in context for x in [
                    "weight", "g.v.w", "engine", "chassis", "policy", "tcf"
                    ]):
                    continue

                # Reject model year (very important)
                if 1900 <= value <= 2099:
                    continue

                data["number_of_passengers"] = str(value)
                break

    # Vehicle type / make / model

    color_words = [
        "blue", "white", "black", "red", "silver", "grey", "gray",
        "brown", "green", "yellow", "gold", "beige", "orange"
        ]

    for i, line in enumerate(lines):
        if "veh" in line.lower() and "type" in line.lower():
            nearby = lines[max(0, i - 5): min(len(lines), i + 5)]

            for candidate in nearby:
                candidate = re.sub(r"\s+", " ", candidate).strip()
                candidate_lower = candidate.lower()

                if not re.search(r"[A-Za-z]{2,}", candidate):
                    continue

                if candidate_lower in color_words:
                    continue

                if any(x in candidate_lower for x in [
                    "veh", "type", "vehicle information", "model", "origin",
                    "g.v.w", "empty", "weight", "engine", "eng", "chassis",
                    "licensing", "authority", "uae", "rta","color","colour"
                    ]):
                    continue

                if candidate.title() == data.get("origin"):
                    continue

                data["vehicle_type"] = candidate.title()

                parts = data["vehicle_type"].split()
                if parts:
                    data["make"] = parts[0].title()

                if len(parts) > 1:
                    data["model"] = " ".join(parts[1:]).title()

                break

        if "vehicle_type" in data:
            break


    # Vehicle type fallback: scan all lines

    if "vehicle_type" not in data:
        for line in lines:
            candidate = re.sub(r"\s+", " ", line).strip()
            candidate_lower = candidate.lower()

            if not re.search(r"[A-Za-z]{2,}", candidate):
                continue

            if any(x in candidate_lower for x in [
                "vehicle information", "licensing authority", "origin",
                "model", "uae", "rta", "empty", "weight",
                "chassis", "eng", "pass", "g.v.w","color","colour"
                ]):
                continue

            if candidate.title() == data.get("origin"):
                continue

            
            data["vehicle_type"] = candidate.title()
            parts = data["vehicle_type"].split()
            if parts:
                data["make"] = parts[0].title()

            if len(parts) > 1:
                data["model"] = " ".join(parts[1:]).title()

            break

    
    # ---------------- CHASSIS NO ----------------
    chassis_candidates = re.findall(r"\b[A-HJ-NPR-Z0-9]{17}\b", compact_text.upper())

    for chassis in chassis_candidates:
        if not chassis.startswith(("STMT", "EPM","UAE","RTA")):
            data["chassis_no"] = chassis
            break
    
    #fallback : 
    if "chassis_no" not in data:
        for i, line in enumerate(lines):
            if "chassis" in line.lower() or "القاعدة" in line:
                nearby = lines[max(0, i - 3): min(len(lines), i + 5)]

                for item in nearby:
                    candidate = re.sub(r"[^A-Za-z0-9]", "", item).upper()

                    if (
                        15 <= len(candidate) <= 18
                        and re.search(r"[A-Z]", candidate)
                        and re.search(r"\d", candidate)
                        and not candidate.startswith(("UAE", "RTA", "WWW","STMT","EPM"))
                        ):
                        data["chassis_no"] = candidate
                        break

            if "chassis_no" in data:
                break

    # ---------------- ENGINE NO ----------------
    # Engine No
    if "engine_no" not in data:
        for i, line in enumerate(lines):
            if "eng" in line.lower() or "المحرك" in line:
                nearby = lines[max(0, i - 4): min(len(lines), i + 5)]

                for item in nearby:
                    candidate = re.sub(r"[^A-Za-z0-9]", "", item).upper()

                    if not candidate:
                        continue

                    if candidate == data.get("chassis_no"):
                        continue

                    if candidate.startswith(("UAE", "RTA", "WWW", "STMT", "EPM")):
                        continue

                # chassis/VIN is usually 17 chars, don't treat it as engine
                    if len(candidate) == 17:
                        continue
                    if candidate in ["EMPTYWEIGHT", "GVW", "WEIGHT", "VEHTYPE", "MODEL", "ORIGIN"]:
                        continue

                   # reject weights like 2400KG, 1800KG, 1100
                    if re.fullmatch(r"\d{3,5}K?G?", candidate):
                        continue

                # allow numeric-only and alphanumeric engine numbers
                    if (5 <= len(candidate) <= 15 and re.search(r"\d", candidate)):
                        data["engine_no"] = candidate
                        break

            if "engine_no" in data:
                break


    # FINAL FORCE PLACE OF ISSUE FALLBACK 
    if "place_of_issue" not in data:
        compact_arabic = re.sub(r"\s+", "", "\n".join(lines))

        if "دبي" in compact_arabic or "دبى" in compact_arabic:
            data["place_of_issue"] = "Dubai"
            data["plate_source"] = "Dubai"

        elif "ابوظبي" in compact_arabic or "أبوظبي" in compact_arabic:
            data["place_of_issue"] = "Abu Dhabi"
            data["plate_source"] = "Abu Dhabi"

        elif "الشارقة" in compact_arabic or "شارقة" in compact_arabic:
            data["place_of_issue"] = "Sharjah"
            data["plate_source"] = "Sharjah"

        elif "عجمان" in compact_arabic:
            data["place_of_issue"] = "Ajman"
            data["plate_source"] = "Ajman"

        elif "راسالخيمة" in compact_arabic or "رأسالخيمة" in compact_arabic:
            data["place_of_issue"] = "Ras Al Khaimah"
            data["plate_source"] = "Ras Al Khaimah"

        elif "الفجيرة" in compact_arabic:
            data["place_of_issue"] = "Fujairah"
            data["plate_source"] = "Fujairah"

        elif "امالقيوين" in compact_arabic or "أمالقيوين" in compact_arabic:
            data["place_of_issue"] = "Umm Al Quwain"
            data["plate_source"] = "Umm Al Quwain"


    front_keys = [
        "registration_no",
        "tcf_no",
        "owner",
        "nationality",
        "place_of_issue",
        "plate_source",
        "registration_date",
        "plate_code",
        "plate_number",
        "policy_no",
        ]

    back_keys = [
        "model_year",
        "origin",
        "number_of_passengers",
        "vehicle_type",
        "chassis_no",
        "engine_no",
        "make",
        "model",
        ]

    front_data = {key: data[key] for key in front_keys if key in data}
    back_data = {key: data[key] for key in back_keys if key in data}
    
    strong_back_fields = ["model_year", "origin", "number_of_passengers", "chassis_no"]
    strong_front_fields = ["registration_no", "plate_code", "plate_number", "registration_date", "tcf_no", "owner", "plate_source"]

    back_score = sum(1 for field in strong_back_fields if field in back_data)
    front_score = sum(1 for field in strong_front_fields if field in front_data)

    forced_side = None
    if document_type:
        doc_hint = str(document_type).lower()
        if doc_hint.endswith("_front"):
            forced_side = "front"
        elif doc_hint.endswith("_back"):
            forced_side = "back"

    if forced_side == "front" and front_data:
        validation_errors = validate_mulkiya_front(front_data)
        confidence = calculate_mulkiya_front_confidence(front_data, validation_errors)
        return {
            "document_type": "mulkiya_front",
            "data": front_data,
            "side": "front",
            "mulkiya_side": "front",
            "validation_errors": validation_errors,
            "confidence": confidence,
        }

    if forced_side == "back" and back_data:
        validation_errors = validate_mulkiya_back(back_data)
        confidence = calculate_mulkiya_back_confidence(back_data, validation_errors)
        return {
            "document_type": "mulkiya_back",
            "data": back_data,
            "mulkiya_side": "back",
            "validation_errors": validation_errors,
            "confidence": confidence,
        }

    if front_score >= 4:
        validation_errors = validate_mulkiya_front(front_data)
        confidence = calculate_mulkiya_front_confidence(front_data, validation_errors)

        return {
            "document_type": "mulkiya_front",
            "data": front_data,
            "side": "front",
            "mulkiya_side":"front",
            "validation_errors":validation_errors,
            "confidence": confidence
            }
    
    if back_score >= 2 and ("chassis_no" in back_data or "engine_no" in back_data):
        validation_errors = validate_mulkiya_back(back_data)
        confidence = calculate_mulkiya_back_confidence(back_data, validation_errors)
        return {
            "document_type": "mulkiya_back",
            "data": back_data,
            "mulkiya_side": "back",
            "validation_errors":validation_errors,
            "confidence": confidence
            }

    return {
        "document_type": "mulkiya",
        "values": {**front_data, **back_data},
        "mulkiya_side": "combined"
        }



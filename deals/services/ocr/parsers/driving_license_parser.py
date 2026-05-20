import re
from difflib import SequenceMatcher


def normalize_text(text):
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def clean_value(value):
    return re.sub(r"\s+", " ", (value or "")).strip(" :.-")


def similarity(a, b):
    return SequenceMatcher(None, (a or "").lower(), (b or "").lower()).ratio()


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


def correct_city(value):
    if not value:
        return None

    value_lower = value.lower()

    if "dubal" in value_lower or "duba1" in value_lower:
        return "Dubai"

    cities = [
        "Dubai",
        "Abu Dhabi",
        "Sharjah",
        "Ajman",
        "Fujairah",
        "Ras Al Khaimah",
        "Umm Al Quwain"
    ]

    best = None
    score = 0

    for city in cities:
        s = similarity(value, city)
        if s > score:
            score = s
            best = city

    return best if score > 0.75 else None


def normalize_date(date_str):
    try:
        date_str = date_str.replace("/", "-").replace(".", "-")

        if re.match(r"\d{2}-\d{2}-\d{4}", date_str):
            return date_str

        if re.match(r"\d{2}-[A-Za-z]{3}-\d{2}", date_str):
            d, mon, y = date_str.split("-")

            months = {
                "jan": "01", "feb": "02", "mar": "03",
                "apr": "04", "may": "05", "jun": "06",
                "jul": "07", "aug": "08", "sep": "09",
                "oct": "10", "nov": "11", "dec": "12"
            }

            y = int(y)
            y = 1900 + y if y > 50 else 2000 + y

            return f"{d}-{months[mon.lower()]}-{y}"

    except Exception:
        return None

    return None


def extract_all_dates(text):
    patterns = [
        r"\d{2}[/-]\d{2}[/-]\d{4}",
        r"\d{2}[/-][A-Za-z]{3}[/-]\d{2}"
    ]

    dates = []

    for pattern in patterns:
        matches = re.findall(pattern, text)

        for match in matches:
            normalized = normalize_date(match)

            if normalized and normalized not in dates:
                dates.append(normalized)

    return dates


def detect_front_or_back(text):
    t = normalize_text(text)

    if "traffic code" in t or "permitted vehicles" in t:
        return "back"

    return "front"


def extract_name(text):
    stop_words = [
        "nationality",
        "issue",
        "expiry",
        "date",
        "birth",
        "license",
        "traffic",
        "place",
        "emirates",
        "uae",
        "authority",
        "licensing"
    ]

    def clean_and_stop(value):
        if not value:
            return None

        pattern = r"\b(" + "|".join(stop_words) + r")\b"
        value = re.split(pattern, value, flags=re.I)[0]

        value = re.sub(r"[^A-Za-z\s]", " ", value)
        value = re.sub(r"\s+", " ", value).strip()

        words = value.split()

        if len(words) < 2 or len(words) > 6:
            return None

        return " ".join(w.capitalize() for w in words)

    lines = text.split("\n")

    for i, line in enumerate(lines):
        if "name" in line.lower():
            value = re.sub(r"name\s*[:\-]?", "", line, flags=re.I).strip()
            value = clean_and_stop(value)

            if value:
                return value

            if i + 1 < len(lines):
                value = clean_and_stop(lines[i + 1])

                if value:
                    return value

    match = re.search(
        r"name\s*[:\-]?\s*([A-Za-z\s]{3,}?)\s*(?:nationality|$)",
        text,
        re.I
    )

    if match:
        name = clean_and_stop(match.group(1))

        if name:
            return name

    caps_candidates = re.findall(
        r"\b[A-Z]{2,}(?:\s+[A-Z]{2,}){1,5}\b",
        text
    )

    for candidate in caps_candidates:
        cleaned = clean_and_stop(candidate)

        if cleaned:
            return cleaned

    candidates = re.findall(
        r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,5}\b",
        text
    )

    for candidate in candidates:
        cleaned = clean_and_stop(candidate)

        if cleaned:
            return cleaned

    return None


def extract_place(text):
    match = re.search(
        r"place\s*of\s*issue\s*(.*)",
        text,
        re.I
    )

    if match:
        raw = clean_value(match.group(1))
        city = correct_city(raw)

        if city:
            return city

    for city in [
        "Dubai",
        "Abu Dhabi",
        "Sharjah",
        "Ajman",
        "Fujairah",
        "Ras Al Khaimah",
        "Umm Al Quwain"
    ]:
        if city.lower() in text.lower():
            return city

    return None


def parse_driving_license(
    text=None,
    document_type=None,
    key_values=None,
    tables=None,
    azure_json=None
):
    text = text or ""

    layout_lines = get_lines_from_azure(azure_json)

    if layout_lines:
        text = "\n".join(layout_lines)

    document_type = (document_type or "").lower()

    if document_type == "driving_license_back":
        side = "back"
    elif document_type == "driving_license_front":
        side = "front"
    else:
        side = detect_front_or_back(text)

    data = {}
    confidence = {}

    if side == "front":
        lic = re.search(
            r"(?:license|licence)\s*(?:no|number)?\s*[:\-]?\s*(\d{5,10})",
            text,
            re.I
        )

        if not lic:
            lic = re.search(r"\b\d{5,10}\b", text)

        data["license_no"] = lic.group(1) if lic and lic.lastindex else (
            lic.group() if lic else ""
        )
        confidence["license_no"] = 90 if lic else 0

        name = extract_name(text)
        data["name"] = name or ""
        confidence["name"] = 90 if name else 0

        nationality = ""

        for i, line in enumerate(layout_lines):
            if re.search(r"nat[a-z]*", line, re.I):
                parts = re.split(r"[:\-]", line)

                if len(parts) > 1:
                    candidate = clean_value(parts[1])
                    words = candidate.split()

                    if words and len(words[0]) >= 3:
                        nationality = words[0]

                if not nationality and i + 1 < len(layout_lines):
                    nxt = clean_value(layout_lines[i + 1])
                    words = nxt.split()

                    if words and len(words[0]) >= 3 and not re.search(r"nat[a-z]*", nxt, re.I):
                        nationality = words[0]

                break

        if not nationality:
            match = re.search(
                r"nat(?:i|l)o?n[a-z]*\s*[:\-]?\s*([A-Za-z\s]{3,30})",
                text,
                re.I
            )

            if match:
                candidate = clean_value(match.group(1))
                words = candidate.split()

                if words and len(words[0]) >= 3:
                    nationality = words[0]

        if nationality:
            nationality = re.sub(r"[^A-Za-z\s]", "", nationality).strip()

            if len(nationality) < 3:
                nationality = ""

        data["nationality"] = nationality or ""
        confidence["nationality"] = 85 if nationality else 0

        dates = extract_all_dates(text)

        if len(dates) >= 3:
            data["date_of_birth"] = dates[0]
            data["issue_date"] = dates[1]
            data["expiry_date"] = dates[2]

            confidence["date_of_birth"] = 85
            confidence["issue_date"] = 85
            confidence["expiry_date"] = 85
        else:
            data["date_of_birth"] = ""
            data["issue_date"] = ""
            data["expiry_date"] = ""

            confidence["date_of_birth"] = 0
            confidence["issue_date"] = 0
            confidence["expiry_date"] = 0

        place = extract_place(text)
        data["place_of_issue"] = place or ""
        confidence["place_of_issue"] = 85 if place else 0

    else:
        traffic = re.search(r"\d{6,12}", text)

        data["traffic_code_no"] = traffic.group() if traffic else ""
        confidence["traffic_code_no"] = 85 if traffic else 0

        vehicles = []
        text_clean = normalize_text(text)

        vehicle_keywords = {
            "light vehicle": [
                r"light\s*vehicle",
                r"lightvehic",
                r"lv\b"
            ],
            "motorcycle": [
                r"motor\s*cycle",
                r"motorcycle",
                r"\bmc\b"
            ],
            "heavy vehicle": [
                r"heavy\s*vehicle",
                r"hv\b"
            ],
            "bus": [
                r"\bbus\b"
            ],
        }

        for vehicle, patterns in vehicle_keywords.items():
            for pattern in patterns:
                if re.search(pattern, text_clean, re.I):
                    vehicles.append(vehicle)
                    break

        vehicles = list(set(vehicles))

        data["permitted_vehicles"] = vehicles
        confidence["permitted_vehicles"] = min(70 + (len(vehicles) * 5), 90) if vehicles else 0

    validation_errors = {}

    for key, value in data.items():
        if not value:
            validation_errors[key] = "Not found"

    scores = list(confidence.values())
    confidence["overall_confidence"] = round(sum(scores) / len(scores), 2) if scores else 0

    return {
        "document_type": f"driving_license_{side}",
        "side": side,
        "data": data,
        "values": data,
        "validation_errors": validation_errors,
        "confidence": confidence
    }
import re
from datetime import datetime



#HELPERS
def normalize_date(date_value):
    if not date_value:
        return None

    date_value = date_value.strip()

    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d %m %Y"):
        try:
            return datetime.strptime(date_value, fmt).strftime("%d/%m/%Y")
        except:
            continue

    return None


def clean_value(value):
    if not value:
        return None

    value = re.sub(r'\s+', ' ', value).strip()

    if value.lower() in ["null", "none", "n/a"]:
        return None

    if not any(c.isalnum() for c in value):
        return None

    return value

def ocr_sanitize(text):
    if not text:
        return ""

    text = text.upper()

    text = re.sub(r"\b(ENG|BRUK|DANS|DOB|DATE OF BIRTH|ISSUING|EXPIRY)\b", " ", text)

    text = re.sub(r"[\u0600-\u06FF]+", " ", text)

    text = re.sub(r"\s+", " ", text).strip()

    return text

def clean_nationality(value):
    if not value:
        return None

    value = value.upper()

    value = re.sub(r"\b(ENG|BRUK|DOB|DATE|ISSUING|EXPIRY|SEX)\b", "", value)
    value = re.sub(r"[^A-Z\s]", "", value)
    value = re.sub(r"\s+", " ", value).strip()

    return value.title() if value else None


def confidence_score(value, field_type="generic"):
    if not value:
        return 0.0

    value = str(value).strip()
    score = 40.0 

    if field_type == "emirates_id":
        if re.fullmatch(r"784-\d{4}-\d{7}-\d", value):
            score = 95.0
        else:
            score = 60.0

    elif field_type == "date":
        try:
            datetime.strptime(value, "%d/%m/%Y")
            score = 90.0
        except:
            score = 30.0

    elif field_type == "name":
        words = value.split()

        if len(words) >= 2:
            score = 88.0

        # penalty for OCR noise words inside name
        noise_words = ["DATE", "NATIONALITY", "ISSUING", "EXPIRY", "SEX"]
        if any(n in value.upper() for n in noise_words):
            score -= 15

    elif field_type == "gender":
        if value in ["M", "F"]:
            score = 95.0
        else:
            score = 30.0

    elif field_type == "nationality":
        clean = re.sub(r"[^A-Z\s]", "", value.upper())
        clean = re.sub(r"\s+", " ", clean).strip()
        words = clean.split()

        valid_countries = {
            "INDIA", "UAE", "PAKISTAN", "NEPAL",
            "BANGLADESH", "SRI LANKA",
            "PHILIPPINES", "EGYPT",
            "YEMEN", "JORDAN", "SYRIA",
            "IRAQ", "IRAN", "OMAN",
            "SAUDI ARABIA"
        }

        # EXACT MATCH → highest confidence
        if clean in valid_countries:
            score = 92.0

        # SINGLE WORD BUT VALID COUNTRY
        elif len(words) == 1 and words[0] in valid_countries:
            score = 90.0

        # PARTIAL / OCR NOISE MIX
        elif any(w in valid_countries for w in words):
            score = 65.0

        # INVALID
        else:
            score = 25.0

    return max(0.0, min(score, 100.0))


def _apply_azure_name_fields(
    data: dict,
    confidence: dict,
    key_values: dict[str, str] | None,
) -> None:
    """Prefer Azure structured ``Name`` / FirstName+LastName when present."""
    if not key_values:
        return

    azure_name = key_values.get("Name") or key_values.get("name")
    if azure_name and not data.get("name"):
        cleaned_name = clean_value(azure_name)
        if cleaned_name:
            data["name"] = cleaned_name
            confidence["name"] = confidence_score(cleaned_name, "name")

    if data.get("name"):
        return

    first = key_values.get("FirstName") or key_values.get("first_name") or ""
    last = key_values.get("LastName") or key_values.get("last_name") or ""
    combined = clean_value(f"{first} {last}".strip())
    if combined:
        data["name"] = combined
        confidence["name"] = confidence_score(combined, "name")


# FRONT PARSER
def parse_emirates_id_front(text, key_values=None):

    if not text:
        data: dict = {"name": None}
        confidence: dict = {}
        _apply_azure_name_fields(data, confidence, key_values)
        if data.get("name"):
            return {
                "document_type": "emirates_id_front",
                "side": "front",
                "data": data,
                "values": data,
                "validation_errors": {},
                "confidence": confidence,
            }
        return {
            "document_type": "emirates_id_front",
            "side": "unknown",
            "data": {},
            "values": {},
            "confidence": {},
            "confidence_score": 0.0,
        }

    data = {
        "emirates_id_number": None,
        "name": None,
        "date_of_birth": None,
        "nationality": None,
        "issuing_date": None,
        "expiry_date": None,
        "sex": None
    }

    confidence = {}

    cleaned = re.sub(r'\s+', ' ', text.upper())
    full_text = cleaned 

    # EMIRATES ID
    id_match = re.search(r'784[\s-]?\d{4}[\s-]?\d{7}[\s-]?\d', cleaned)

    if id_match:
        raw = re.sub(r'[\s-]', '', id_match.group())
        data["emirates_id_number"] = f"{raw[:3]}-{raw[3:7]}-{raw[7:14]}-{raw[14]}"
        confidence["emirates_id_number"] = confidence_score(
            data["emirates_id_number"], "emirates_id"
        )

    #name
    name_match = re.search(
        r'NAME[:\s]*([A-Z\s]{3,}?)(?=NATIONALITY|DATE OF BIRTH|DOB|ISSUING|EXPIRY|SEX|$)',
        cleaned
    )

    if name_match:
        name = name_match.group(1)
        name = re.split(
            r'NATIONALITY|DATE OF BIRTH|DOB|ISSUING|EXPIRY|SEX',
            name
        )[0].strip()

        data["name"] = clean_value(name.title())
        confidence["name"] = confidence_score(data["name"], "name")

    if not data["name"]:
        fallback = re.findall(r'\b[A-Z]{3,}\s[A-Z]{3,}\s[A-Z]{3,}', cleaned)
        if fallback:
            data["name"] = clean_value(fallback[0].title())
            confidence["name"] = confidence_score(data["name"], "name")

    # DOB
    dob_match = re.search(r'(DOB|DATE OF BIRTH).*?(\d{2}[/-]\d{2}[/-]\d{4})',cleaned)

    if not dob_match:
        dob_match = re.search(r'\b\d{2}[/-]\d{2}[/-]\d{4}\b', cleaned)

    if dob_match:
        date_str = dob_match.group(2) if dob_match.lastindex else dob_match.group(0)
        data["date_of_birth"] = normalize_date(date_str)
        confidence["date_of_birth"] = confidence_score(data["date_of_birth"], "date")


    # NATIONALITY
    nat = re.search(r"NATIONALITY[:\s]+([A-Z\s]+)", full_text)

    if nat:
        nat_val = nat.group(1)
        nat_val = re.sub(r"\b(ENG|BRUK|DANS|DOB|DATE|ISSUING|EXPIRY|SEX)\b"," ",nat_val)
        nat_val = re.sub(r"[^A-Z\s]", " ", nat_val)
        nat_val = re.sub(r"\s+", " ", nat_val).strip()
        tokens = nat_val.split()

        if tokens:
            clean_nat = tokens[0]  # keeps only "India"
            if len(clean_nat) >= 3:
                data["nationality"] = clean_nat.title()
            else:
                data["nationality"] = None
        else:
            data["nationality"] = None
        
        confidence["nationality"] = confidence_score(data["nationality"],"nationality")


    # ISSUING DATE
    issue = re.search(r'ISSUING DATE.*?(\d{2}[/-]\d{2}[/-]\d{4})', cleaned)

    if issue:
        data["issuing_date"] = normalize_date(issue.group(1))
        confidence["issuing_date"] = confidence_score(data["issuing_date"], "date")

    # EXPIRY DATE
    expiry = re.search(r'EXPIRY DATE.*?(\d{2}[/-]\d{2}[/-]\d{4})', cleaned)

    if expiry:
        data["expiry_date"] = normalize_date(expiry.group(1))
        confidence["expiry_date"] = confidence_score(data["expiry_date"], "date")

    # SEX
    sex = re.search(r'SEX[:\s]*([MF])', cleaned)

    if sex:
        data["sex"] = sex.group(1)
        confidence["sex"] = confidence_score(data["sex"], "gender")

    if data.get("name"):
        data["name"] = re.sub(
            r"(DATE OF BIRTH|DOB|NATIONALITY|ISSUING|EXPIRY|SEX).*",
            "",
            data["name"],
            flags=re.IGNORECASE
        ).strip()

    _apply_azure_name_fields(data, confidence, key_values)

    overall_confidence = round(sum(confidence.values()) / len(confidence) if confidence else 0,2)

    return {
        "document_type": "emirates_id_front",
        "side": "front",
        "data": data,
        "values":data,
        "validation_errors":{},
        "confidence": {
            **confidence,
            "overall_confidence": overall_confidence
            }
    }



# BACK PARSER
def parse_emirates_id_back(text):

    if not text:
        return {
            "document_type": "emirates_id_back",
            "side": "unknown",
            "data": {},
            "values":{},
            "confidence": {},
            "confidence_score": 0.0
        }

    data = {
        "card_number": None,
        "occupation": None,
        "employer": None,
        "family_sponsor": None,
        "issuing_place": None
    }

    confidence = {}

    cleaned = text.upper()

    # Card number
    card = re.search(
        r'Card\s*Number[\s\S]{0,40}?(\d{6,12})',
        text,
        re.IGNORECASE
    )

    if not card:
        # fallback: first standalone 6-12 digit number near top of back side
        card = re.search(r'\b\d{6,12}\b', text)

    if card:
        data["card_number"] = card.group(1) if card.lastindex else card.group(0)
        confidence["card_number"] = 90.0
    # card = re.search(r'CARD NUMBER[:\s]*([0-9]{6,12})', cleaned)
    # if card:
    #     data["card_number"] = card.group(1)
    #     confidence["card_number"] = 90.0

    # Occupation
    occ = re.search(r'Occupation\s*[:\-]?\s*(.+)', text, re.IGNORECASE)
    if occ:
        data["occupation"] = clean_value(occ.group(1).split("\n")[0])
        confidence["occupation"] = 85.0

    # Employer
    emp = re.search(r'Employer\s*[:\-]?\s*(.+)', text, re.IGNORECASE)
    if emp:
        data["employer"] = clean_value(emp.group(1).split("\n")[0])
        confidence["employer"] = 85.0

    # Family sponsor
    fam = re.search(r'Family Sponsor\s*[:\-]?\s*(.+)', text, re.IGNORECASE)
    if fam:
        data["family_sponsor"] = clean_value(fam.group(1).split("\n")[0])
        confidence["family_sponsor"] = 85.0

    # Issuing place
    place = re.search(r'Issuing Place\s*[:\-]?\s*(.+)', text, re.IGNORECASE)
    if place:
        data["issuing_place"] = clean_value(place.group(1).split("\n")[0])
        confidence["issuing_place"] = 85.0

    overall_confidence = round(
        sum(confidence.values()) / len(confidence) if confidence else 0,
        2
    )

    return {
        "document_type": "emirates_id_back",
        "side": "back",
        "data": data,
        "values":data,
        "validation_errors":{},
        "confidence": {
            **confidence,
            "overall_confidence": overall_confidence
        }
    }

#main entry
def parse_emirates_id(text, document_type=None, key_values=None, tables=None):
    document_type = (document_type or "").lower()

    if document_type == "emirates_id_back":
        return parse_emirates_id_back(text)

    if document_type == "emirates_id_front":
        return parse_emirates_id_front(text, key_values=key_values)

    # default if frontend does not specify side
    return parse_emirates_id_front(text, key_values=key_values)

# def parse_emirates_id(text, document_type=None):

#     if document_type == "emirates_id_back":
#         return parse_emirates_id_back(text)

#     return parse_emirates_id_front(text)
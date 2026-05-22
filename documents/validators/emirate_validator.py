import re
from datetime import datetime

# CONSTANTS
UAE_EMIRATES = [
    "dubai",
    "abu dhabi",
    "sharjah",
    "ajman",
    "umm al quwain",
    "ras al khaimah",
    "fujairah"
]

# HELPERS
def is_empty(value):
    return value in [None, "", "null", "None"]


def is_valid_date(date_str):
    try:
        return datetime.strptime(date_str, "%d/%m/%Y")
    except:
        return None


def calculate_age(dob):
    today = datetime.today()
    return (today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day)))


# MAIN VALIDATOR
def validate_emirates_id(parsed_data):

    values = parsed_data.get("data", {}) or {}

    errors = {}

    doc_type = parsed_data.get("document_type", "")
    side = parsed_data.get("side", "unknown")

    # FRONT VALIDATION
    if doc_type == "emirates_id_front":

        required = [
            "emirates_id_number",
            "name",
            "date_of_birth",
            "nationality",
            "expiry_date"
        ]

        for field in required:
            if is_empty(values.get(field)):
                errors[field] = "Missing field"

        # Emirates ID format
        eid = values.get("emirates_id_number")
        if eid:
            if not re.match(r"^784-\d{4}-\d{7}-\d$", eid):
                errors["emirates_id_number"] = "Invalid format"

        # Name validation
        name = values.get("name")
        if name:
            if len(name.split()) < 2:
                errors["name"] = "Must contain at least 2 words"

        # DOB validation
        dob_str = values.get("date_of_birth")
        dob = is_valid_date(dob_str) if dob_str else None

        if dob:
            age = calculate_age(dob)
            if age < 0 or age > 120:
                errors["date_of_birth"] = "Invalid age"
        elif dob_str:
            errors["date_of_birth"] = "Invalid date format"

        # Nationality
        nationality = values.get("nationality")
        if nationality:
            if len(nationality.strip()) < 3:
                errors["nationality"] = "Invalid nationality"

        # Gender
        sex = values.get("sex")
        if sex:
            if sex not in ["M", "F"]:
                errors["sex"] = "Invalid gender"

        # Issuing date
        issue = values.get("issuing_date")
        if issue and not is_valid_date(issue):
            errors["issuing_date"] = "Invalid date format"

        # Expiry date
        expiry = values.get("expiry_date")
        expiry_dt = is_valid_date(expiry) if expiry else None
        issue_dt = is_valid_date(issue) if issue else None

        if expiry and not expiry_dt:
            errors["expiry_date"] = "Invalid date format"

        if expiry_dt and issue_dt and expiry_dt <= issue_dt:
            errors["expiry_date"] = "Must be after issuing date"

        side = "front"

    # BACK VALIDATION
    elif doc_type == "emirates_id_back":

        required = [
            "card_number",
            "issuing_place"
        ]

        for field in required:
            if is_empty(values.get(field)):
                errors[field] = "Missing field"

        # Card number
        card = values.get("card_number")
        if card:
            if not re.fullmatch(r"\d{6,12}", str(card)):
                errors["card_number"] = "Invalid card number format"

        # Issuing place (emirate check)
        place = values.get("issuing_place")
        if place:
            normalized_place = place.strip().lower()

            if normalized_place not in UAE_EMIRATES:
                errors["issuing_place"] = "Invalid UAE emirate"

        side = "back"

    # UNKNOWN DOC TYPE
    else:
        return {
            "status": "PENDING",
            "errors": {
                "document": "Unknown document type"
            },
            "side": "unknown"
        }

    # FINAL OUTPUT
    return {
        "status": "VERIFIED" if not errors else "PENDING",
        "errors": errors,
        "side": side
    }
import re
from datetime import datetime


def is_empty(value):
    return value in [None, "", [], "null", "None"]


def is_valid_date(date_str):
    if not date_str:
        return None

    for fmt in ("%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    return None


def validate_driving_license(parsed_data):
    values = parsed_data.get("values") or parsed_data.get("data") or {}
    doc_type = (parsed_data.get("document_type") or "").lower()
    side = parsed_data.get("side", "unknown")

    errors = {}

    if doc_type == "driving_license_front" or side == "front":
        required = [
            "license_no",
            "name",
            "nationality",
            "date_of_birth",
            "issue_date",
            "expiry_date",
            "place_of_issue",
        ]

        for field in required:
            if is_empty(values.get(field)):
                errors[field] = "Missing field"

        license_no = values.get("license_no")
        if license_no and not re.fullmatch(r"\d{5,10}", str(license_no)):
            errors["license_no"] = "Invalid license number format"

        name = values.get("name")
        if name and len(name.split()) < 2:
            errors["name"] = "Must contain at least 2 words"

        dob = values.get("date_of_birth")
        issue = values.get("issue_date")
        expiry = values.get("expiry_date")

        dob_dt = is_valid_date(dob)
        issue_dt = is_valid_date(issue)
        expiry_dt = is_valid_date(expiry)

        if dob and not dob_dt:
            errors["date_of_birth"] = "Invalid date format"

        if issue and not issue_dt:
            errors["issue_date"] = "Invalid date format"

        if expiry and not expiry_dt:
            errors["expiry_date"] = "Invalid date format"

        if issue_dt and expiry_dt and expiry_dt <= issue_dt:
            errors["expiry_date"] = "Must be after issue date"

        if dob_dt and issue_dt and issue_dt <= dob_dt:
            errors["issue_date"] = "Must be after date of birth"

        side = "front"

    elif doc_type == "driving_license_back" or side == "back":
        required = [
            "traffic_code_no",
            "permitted_vehicles",
        ]

        for field in required:
            if is_empty(values.get(field)):
                errors[field] = "Missing field"

        traffic_code_no = values.get("traffic_code_no")
        if traffic_code_no and not re.fullmatch(r"\d{6,12}", str(traffic_code_no)):
            errors["traffic_code_no"] = "Invalid traffic code format"

        permitted_vehicles = values.get("permitted_vehicles")
        if permitted_vehicles and not isinstance(permitted_vehicles, list):
            errors["permitted_vehicles"] = "Must be a list"

        side = "back"

    else:
        errors["document"] = "Unknown driving license side"

    return {
        "status": "VERIFIED" if not errors else "PENDING",
        "errors": errors,
        "side": side
    }
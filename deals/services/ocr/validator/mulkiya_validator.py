import re


def _is_valid_registration_no(values: dict) -> bool:
    """Accept digits-only plate number or ``CODE/NUMBER`` (as on the card)."""
    registration_no = str(values.get("registration_no") or "").strip().upper()
    if not registration_no:
        return False

    plate_number = str(values.get("plate_number") or "").strip()
    if plate_number and registration_no == plate_number.upper():
        return bool(re.fullmatch(r"\d{3,6}", registration_no))

    if "/" in registration_no:
        return bool(re.fullmatch(r"[A-Z0-9]{1,3}/\d{3,6}", registration_no))

    return bool(re.fullmatch(r"\d{3,6}", registration_no))


def validate_mulkiya(data):
    errors = {}

    document_type = data.get("document_type")
    values = data.get("data") or data.get("values") or {}

    front_required = [
        "registration_no",
        "tcf_no",
        "owner",
        "registration_date",
        "plate_code",
        "plate_number",
        "place_of_issue",
    ]

    back_required = [
        "model_year",
        "origin",
        "number_of_passengers",
        "vehicle_type",
        "chassis_no",
    ]

    if not values:
        return {
            "status": "PENDING",
            "errors": {"document": "No Mulkiya fields extracted"},
            "side": "unknown"
        }

    if document_type == "mulkiya_front":
        required_fields = front_required
        side = "front"

    elif document_type == "mulkiya_back":
        required_fields = back_required
        side = "back"

    else:
        required_fields = front_required + back_required
        side = "combined"

    for field in required_fields:
        if not values.get(field):
            errors[field] = "Missing field"

    if values.get("registration_no") and not _is_valid_registration_no(values):
        errors["registration_no"] = "Invalid registration number format"

    if values.get("tcf_no") and not values["tcf_no"].isdigit():
        errors["tcf_no"] = "Invalid TCF number format"

    if values.get("owner") and len(values["owner"].split()) < 2:
        errors["owner"] = "Owner name looks incomplete"

    return {
        "status": "PENDING" if errors else "VERIFIED",
        "errors": errors,
        "side": side
    }





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

    if values.get("registration_no") and "/" not in values["registration_no"]:
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





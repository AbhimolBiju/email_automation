def validate_adamjee_credit_note(data):

    required_fields = [
        "invoice_number",
        "invoice_date",
        "insured_name",
        "policy_number",
        "total_amount",
    ]

    missing_fields = []

    for field in required_fields:

        value = data.get(field)

        if value is None or str(value).strip() == "":
            missing_fields.append(field)

    is_valid = len(missing_fields) == 0

    return {
        "is_valid": is_valid,
        "missing_fields": missing_fields,
        "message": (
            "Adamjee credit note validated successfully"
            if is_valid
            else "Missing required fields"
        )
    }
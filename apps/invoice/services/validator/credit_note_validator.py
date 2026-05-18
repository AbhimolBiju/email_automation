def validate_required_fields(
    data,
    required_fields,
    document_name="Document",
):

    missing_fields = []

    for field in required_fields:

        value = data.get(field)

        if (
            value is None
            or str(value).strip() == ""
        ):
            missing_fields.append(field)

    is_valid = len(missing_fields) == 0

    return {
        "is_valid": is_valid,
        "missing_fields": missing_fields,
        "message": (
            f"{document_name} validated successfully"
            if is_valid
            else f"Missing required fields in {document_name}"
        )
    }

def validate_credit_note(data):

    required_fields = [
        "invoice_number",
        "invoice_date",
        "insured_name",
        "policy_number",
        "total_amount",
    ]

    return validate_required_fields(
        data=data,
        required_fields=required_fields,
        document_name="Credit Note",
    )
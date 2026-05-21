from .credit_note_validator import validate_required_fields


def validate_rak_credit_note(data):
    required_fields = [
        "invoice_number",
        "invoice_date",
        "broker_name",
        "insured_name",
        "policy_number",
        "policy_type",
        "commission_amount",
        "total_amount",
    ]

    return validate_required_fields(
        data=data,
        required_fields=required_fields,
        document_name="RAK Credit Note",
    )
from .credit_note_validator import validate_required_fields

def validate_arabia_credit_note(data):
    required_fields = [
        "invoice_number",
        "invoice_date",
        "broker_name",
        "policy_number",
        "commission_amount",
        "vat_amount",
        "total_amount",
    ]

    return validate_required_fields(
        data=data,
        required_fields=required_fields,
        document_name="Arabia Credit Note",
    )
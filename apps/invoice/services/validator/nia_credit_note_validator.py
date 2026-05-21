from .credit_note_validator import validate_required_fields


def validate_nia_credit_note(data):

    required_fields = [
        "invoice_number",
        "invoice_date",
        "insured_name",
        "total_amount",
        "policy_number",
    ]

    return validate_required_fields(
        data=data,
        required_fields=required_fields,
        document_name="NIA Credit Note",
    )

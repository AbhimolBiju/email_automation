from .credit_note_validator import validate_required_fields


def validate_fidelity_debit_note(data):
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
        document_name="Fidelity Debit Note",
    )




# def validate_fidelity_debit_note(parsed_data):
#     required_fields = [
#         "document_type",
#         "invoice_date",
#         "invoice_number",
#         "account_number",
#         "insured_name",
#         "policy_number",
#         "vehicle_reg_no",
#         "chassis_number",
#         "premium_amount",
#         "vat_amount",
#         "total_amount",
#     ]

#     missing_fields = []

#     for field in required_fields:
#         if not parsed_data.get(field):
#             missing_fields.append(field)

#     is_valid = len(missing_fields) == 0

#     return {
#         "is_valid": is_valid,
#         "missing_fields": missing_fields,
#         "message": "Valid document" if len(missing_fields) == 0 else "Missing required fields",
#     }
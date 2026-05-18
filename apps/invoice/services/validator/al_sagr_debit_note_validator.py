def validate_al_sagr_debit_note(parsed_data):
    required_fields = [
        "insurer_name",
        "invoice_date",
        "invoice_number",
        "policy_number",
        "policy_start_date",
        "policy_end_date",
        "net_premium",
        "vat_amount",
        "total",
    ]

    missing_fields = []

    for field in required_fields:
        value = parsed_data.get(field)

        if value is None or str(value).strip() == "":
            missing_fields.append(field)

    return {
        "is_valid": len(missing_fields) == 0,
        "missing_fields": missing_fields,
        "message": (
            "Al Sagr debit note validation passed"
            if len(missing_fields) == 0
            else "Al Sagr debit note validation failed"
        ),
    }



# def validate_al_sagr_debit_note(parsed_data):
#     required_fields = [
#         "document_type",
#         "company_name",
#         "invoice_date",
#         "invoice_number",
#         "account_number",
#         "insured_name",
#         "policy_number",
#         "class_of_insurance",
#         "period_from",
#         "period_to",
#         "premium_amount",
#         "vat_amount",
#         "total_amount",
#     ]

#     missing_fields = []

#     for field in required_fields:
#         value = parsed_data.get(field)

#         if value is None or str(value).strip() == "":
#             missing_fields.append(field)

#     return {
#         "is_valid": len(missing_fields) == 0,
#         "missing_fields": missing_fields,
#         "message": (
#             "Al Sagr debit note validation passed"
#             if len(missing_fields) == 0
#             else "Al Sagr debit note validation failed"
#         ),
#     }
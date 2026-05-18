def map_credit_note_to_form(parsed_data):
    return {
        # Do not force this. Backend dropdown handles it.
        "payment_type": None,

        "insurer_name": parsed_data.get("insurer_name") or parsed_data.get("company_name"),
        "invoice_date": parsed_data.get("invoice_date"),

        "policy_start_date": parsed_data.get("policy_start_date"),
        "policy_end_date": parsed_data.get("policy_end_date"),

        "premium_currency": parsed_data.get("premium_currency", "AED"),

        "branch": parsed_data.get("branch"),
        "policy_type": parsed_data.get("policy_type"),
        "policy_number": parsed_data.get("policy_number"),

        # Credit note invoice number
        "commission_invoice_number": parsed_data.get("invoice_number"),

        # Credit note values usually go to commission/credit side
        "commission_amount": parsed_data.get("commission_amount"),
        "commission_percentage": parsed_data.get("commission_percentage"),
        "vat_amount": parsed_data.get("vat_amount"),
        "total_amount": parsed_data.get("total_amount"),

        "broker_name": parsed_data.get("broker_name"),
        "insured_name": parsed_data.get("insured_name"),
    }
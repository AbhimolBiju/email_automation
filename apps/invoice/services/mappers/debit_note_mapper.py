def map_debit_note_to_form(parsed_data):
    return {
        # Do not force this. Backend dropdown handles it.
        "payment_type": None,

        "insurer_name": parsed_data.get("insurer_name"),
        "invoice_date": parsed_data.get("invoice_date"),

        "policy_start_date": parsed_data.get("policy_start_date"),
        "policy_end_date": parsed_data.get("policy_end_date"),

        "premium_currency": parsed_data.get("premium_currency", "AED"),
        "premium_amount": parsed_data.get("total_amount"),

        "branch": parsed_data.get("branch"),
        "policy_type": parsed_data.get("policy_type"),
        "policy_number": parsed_data.get("policy_number"),

        "tax_invoice_number": parsed_data.get("invoice_number"),

        # Debit note values go to CUSTOMER row
        "customer_net_premium": parsed_data.get("net_premium"),
        "customer_vat_amount": parsed_data.get("vat_amount"),
        "customer_total_premium": parsed_data.get("total_amount"),

        # Insurance company row empty/default
        "company_net_premium": None,
        "company_vat_amount": None,
        "company_total_premium": None,

        "direct_paid_amount": parsed_data.get("total_amount"),

        "broker_name": parsed_data.get("broker_name"),
        "insured_name": parsed_data.get("insured_name"),
    }
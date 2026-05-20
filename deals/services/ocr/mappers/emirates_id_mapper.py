def map_emirates_id_to_form(parsed_data):
    values = parsed_data.get("values") or parsed_data.get("data") or {}
    full_name = values.get("name")

    return {
        "name": full_name,
        "customer_name": full_name,
        "nationality": values.get("nationality"),
        "emirates_id": values.get("emirates_id_number"),
        "id_expiry_date": values.get("expiry_date"),
        "date_of_birth": values.get("date_of_birth"),
        "gender": values.get("sex"),
        "card_number": values.get("card_number"),
        "occupation": values.get("occupation"),
        "employer": values.get("employer"),
        "family_sponsor": values.get("family_sponsor"),
        "emirate": values.get("issuing_place"),
        "issuing_place": values.get("issuing_place"),
    }
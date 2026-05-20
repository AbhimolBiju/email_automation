def map_mulkiya_to_form(parsed_data):
    values = parsed_data.get("values") or parsed_data.get("data") or {}
    owner = values.get("owner")
    plate_source = values.get("plate_source") or values.get("place_of_issue")

    return {
        "name": owner,
        "customer_name": owner,
        "chassis_no": values.get("chassis_no"),
        "registration_no": values.get("registration_no"),
        "registration_date": values.get("registration_date"),
        "plate_code": values.get("plate_code"),
        "plate_source": plate_source,
        "place_of_issue": plate_source,
        "tcf_no": values.get("tcf_no"),
        "tcf_number": values.get("tcf_no"),
        "model_year": values.get("model_year"),
        "make_id": values.get("make"),
        "model_id": values.get("model"),
        "body_type_id": values.get("vehicle_type"),
        "nationality": values.get("nationality"),
        "origin": values.get("origin"),
        "number_of_passengers": values.get("number_of_passengers"),
        "engine_no": values.get("engine_no"),
        "owner": owner,
        "policy_no": values.get("policy_no"),
    }
def map_driving_license_to_form(parsed_data):
    values = parsed_data.get("values") or parsed_data.get("data") or {}
    full_name = values.get("name")
    place_of_issue = values.get("place_of_issue")
    traffic_code = values.get("traffic_code_no")

    return {
        "license_no": values.get("license_no"),
        "license_from_date": values.get("issue_date"),
        "license_to_date": values.get("expiry_date"),
        "name": full_name,
        "customer_name": full_name,
        "nationality": values.get("nationality"),
        "date_of_birth": values.get("date_of_birth"),
        "place_of_issue": place_of_issue,
        "emirate": place_of_issue,
        "tcf_no": traffic_code,
        "tcf_number": traffic_code,
        "traffic_code_no": traffic_code,
        "permitted_vehicles": values.get("permitted_vehicles"),
    }
"""Map parser validation error keys to CRM field keys for enrichment output."""

from __future__ import annotations

# Parser validator key -> CRM key in mapped/enriched output
VALIDATION_ERROR_TO_CRM: dict[str, str] = {
    "emirates_id_number": "emirates_id",
    "name": "name",
    "date_of_birth": "date_of_birth",
    "expiry_date": "id_expiry_date",
    "nationality": "nationality",
    "sex": "gender",
    "issuing_place": "emirate",
    "card_number": "card_number",
    "license_no": "license_no",
    "issue_date": "license_from_date",
    "place_of_issue": "emirate",
    "traffic_code": "tcf_number",
    "registration_no": "registration_no",
    "plate_number": "registration_no",
    "tcf_no": "tcf_number",
    "owner": "name",
    "chassis_no": "chassis_no",
    "plate_code": "plate_code",
    "registration_date": "registration_date",
    "model_year": "model_year",
    "vehicle_type": "body_type_id",
}

# When a field fails validation, related CRM aliases should be removed together.
VALIDATION_ERROR_CASCADE: dict[str, tuple[str, ...]] = {
    "name": ("name", "first_name", "last_name", "customer_name"),
    "owner": ("name", "customer_name"),
    "expiry_date": ("id_expiry_date", "expiry_date"),
    "issue_date": ("license_from_date", "issue_date"),
    "sex": ("gender", "Sex"),
    "issuing_place": ("emirate", "IssuingPlace", "issuing_place"),
    "place_of_issue": ("plate_source", "emirate", "place_of_issue"),
    "traffic_code": ("tcf_number", "traffic_code", "tcf_no"),
    "registration_no": ("registration_no", "reg_number", "RegistrationNumber"),
    "plate_number": ("registration_no", "plate_number"),
    "tcf_no": ("tcf_number", "tcf_no"),
    "emirates_id_number": ("emirates_id", "DocumentNumber", "id_number"),
}

"""Field mapping configuration for OCR target schemas.

Add a new top-level key (e.g. ``"claim_create"``) with per-model Azure field maps.
No mapper logic changes are required.
"""

from __future__ import annotations

# schema_name -> azure_model_id -> { azure_field: crm_field }
FIELD_MAPPING_SCHEMAS: dict[str, dict[str, dict[str, str]]] = {
    "deal_create": {
        "prebuilt-idDocument": {
            "FirstName": "first_name",
            "LastName": "last_name",
            "DateOfBirth": "date_of_birth",
            "DocumentNumber": "emirates_id",
            "id_number": "emirates_id",
            "IDNumber": "emirates_id",
            "identity_number": "emirates_id",
            "gender": "gender",
            "LicenseNumber": "license_no",
            "license_no": "license_no",
            "licence_no": "license_no",
            "Nationality": "nationality",
            "nationality": "nationality",
            "Sex": "gender",
            "DateOfExpiration": "id_expiry_date",
            "license_from_date": "license_from_date",
            "license_to_date": "license_to_date",
            "Address": "customer_address",
            "Region": "emirate",
            "IssuingPlace": "emirate",
            "issuing_place": "emirate",
            "emirate": "emirate",
            "CountryRegion": "customer_city",
            "PostalCode": "customer_pincode",
        },
        "prebuilt-invoice": {
            "CustomerName": "first_name",
            "CustomerAddress": "customer_address",
            "CustomerAddressRecipient": "last_name",
            "InvoiceId": "policy_number",
            "InvoiceDate": "policy_start_date",
            "ServiceStartDate": "policy_start_date",
            "ServiceEndDate": "policy_end_date",
            "DueDate": "policy_end_date",
            "VendorName": "insurer_name",
            "SubTotal": "sum_insured",
            "InvoiceTotal": "premium_amount",
        },
        "prebuilt-document": {
            "LicensePlate": "registration_no",
            "RegistrationNumber": "registration_no",
            "VehicleRegistrationNumber": "registration_no",
            "plate_no": "registration_no",
            "traffic_plate_no": "plate_code",
            "registration_no": "registration_no",
            "reg_number": "registration_no",
            "plate_code": "plate_code",
            "plate_category": "plate_category",
            "plate_source": "plate_source",
            "origin": "plate_source",
            "PlaceOfIssue": "plate_source",
            "place_of_issue": "plate_source",
            "LicensingAuthority": "plate_source",
            "licensing_authority": "plate_source",
            "registration_date": "registration_date",
            "RegDate": "registration_date",
            "Reg_Date": "registration_date",
            "reg_date": "registration_date",
            "tcf_number": "tcf_number",
            "TCFNumber": "tcf_number",
            "TrafficFileNumber": "tcf_number",
            "traffic_file_no": "tcf_number",
            "chassis_no": "chassis_no",
            "Make": "make_id",
            "Model": "model_id",
            "model": "model_id",
            "model_id": "model_id",
            "model_year": "model_year",
            "manufacturer": "make_id",
            "Year": "model_year",
            "ModelYear": "model_year",
            "year": "model_year",
            "VehicleIdentificationNumber": "chassis_no",
            "PolicyNumber": "policy_number",
            "PolicyStartDate": "policy_start_date",
            "PolicyEndDate": "policy_end_date",
            "InsurerName": "insurer_name",
            "SumInsured": "sum_insured",
            "Premium": "premium_amount",
        },
    },
}

# Additional Azure field -> CRM field copies (one Azure value, multiple CRM targets).
SECONDARY_FIELD_MAPPINGS: dict[str, dict[str, dict[str, str]]] = {}

# CRM fields that should be normalized to ISO dates (YYYY-MM-DD).
DATE_FIELDS: set[str] = {
    "date_of_birth",
    "id_expiry_date",
    "license_from_date",
    "license_to_date",
    "policy_start_date",
    "policy_end_date",
    "registration_date",
    "valuation_date",
}

# CRM fields that should be parsed as monetary amounts.
CURRENCY_FIELDS: set[str] = {
    "sum_insured",
    "premium_amount",
}

# CRM fields that should be normalized to Male/Female labels.
GENDER_FIELDS: set[str] = {
    "gender",
}

# CRM fields that should be normalized to English plate source labels.
PLATE_SOURCE_FIELDS: set[str] = {
    "plate_source",
}

# Maps caller ``document_type`` values to Azure prebuilt model IDs.
DOCUMENT_TYPE_MODEL_MAP: dict[str, str] = {
    "id_card": "prebuilt-idDocument",
    "emirates_id": "prebuilt-idDocument",
    "emirates_id_front": "prebuilt-idDocument",
    "emirates_id_back": "prebuilt-idDocument",
    "driving_license": "prebuilt-idDocument",
    "driving_license_front": "prebuilt-idDocument",
    "driving_license_back": "prebuilt-idDocument",
    "national_id": "prebuilt-idDocument",
    "passport": "prebuilt-idDocument",
    "invoice": "prebuilt-invoice",
    "insurance_certificate": "prebuilt-document",
    "policy_document": "prebuilt-document",
    "registration_card": "prebuilt-document",
    "mulkiya_id_front": "prebuilt-document",
    "mulkiya_id_back": "prebuilt-document",
    "mulkiya": "prebuilt-document",
    "other": "prebuilt-document",
}

DEFAULT_AZURE_MODEL = "prebuilt-document"


def resolve_model_id(document_type: str) -> str:
    """Return the Azure model ID for a caller-supplied document type."""
    normalized = (document_type or "other").strip().lower()
    return DOCUMENT_TYPE_MODEL_MAP.get(normalized, DEFAULT_AZURE_MODEL)


def get_schema_mapping(
    target_schema: str,
    model_used: str | None = None,
) -> dict[str, str]:
    """Return the Azure-to-CRM field map for a schema and optional model."""
    schema = FIELD_MAPPING_SCHEMAS.get(target_schema, {})
    if not schema:
        return {}

    first_value = next(iter(schema.values()), None)
    if not isinstance(first_value, dict):
        return {}

    if model_used and model_used in schema:
        return dict(schema[model_used])

    merged: dict[str, str] = {}
    for model_map in schema.values():
        if isinstance(model_map, dict):
            merged.update(model_map)
    return merged


def get_secondary_schema_mapping(
    target_schema: str,
    model_used: str | None = None,
) -> dict[str, str]:
    """Return secondary Azure-to-CRM maps for duplicate target fields."""
    schema = SECONDARY_FIELD_MAPPINGS.get(target_schema, {})
    if not schema:
        return {}

    if model_used and model_used in schema:
        return dict(schema[model_used])

    merged: dict[str, str] = {}
    for model_map in schema.values():
        if isinstance(model_map, dict):
            merged.update(model_map)
    return merged


def list_supported_schemas() -> list[str]:
    """Return registered target schema names."""
    return list(FIELD_MAPPING_SCHEMAS.keys())


def schema_exists(target_schema: str) -> bool:
    """Check whether a target schema is registered."""
    return target_schema in FIELD_MAPPING_SCHEMAS

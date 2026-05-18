"""Field mapping configuration for invoice target schemas.

Add a new top-level key (e.g. ``"billing_create"``) with per-model Azure field maps.
No mapper logic changes are required.
"""

from __future__ import annotations

# schema_name -> azure_model_id -> { azure_field: crm_field }
FIELD_MAPPING_SCHEMAS: dict[str, dict[str, dict[str, str]]] = {
    "invoice_create": {
        "prebuilt-invoice": {
            "InvoiceId": "invoice_no",
            "InvoiceDate": "invoice_date",
            "DueDate": "due_date",
            "VendorName": "vendor_name",
            "VendorAddress": "vendor_address",
            "CustomerName": "customer_name",
            "CustomerAddress": "customer_address",
            "CustomerAddressRecipient": "customer_name",
            "SubTotal": "subtotal",
            "TotalTax": "tax_amount",
            "InvoiceTotal": "total_amount",
            "AmountDue": "amount_due",
            "PurchaseOrder": "purchase_order",
            "BillingAddress": "billing_address",
            "ShippingAddress": "shipping_address",
            "ServiceStartDate": "service_start_date",
            "ServiceEndDate": "service_end_date",
        }
    }
}

SECONDARY_FIELD_MAPPINGS: dict[str, dict[str, dict[str, str]]] = {}

DATE_FIELDS: set[str] = {
    "invoice_date",
    "due_date",
    "service_start_date",
    "service_end_date",
    "policy_start_date",
    "policy_end_date",
}

CURRENCY_FIELDS: set[str] = {
    "subtotal",
    "tax_amount",
    "total_amount",
    "amount_due",
    "premium_amount",
}

# CRM keys produced by invoice_parser enrichment (pass-through in field_mapper).
PARSER_ENRICHED_FIELDS: set[str] = {
    "branch",
    "insurer_name",
    "policy_type",
    "policy_start_date",
    "policy_end_date",
    "premium_amount",
    "premium_currency",
    "invoice_no",
}

DOCUMENT_TYPE_MODEL_MAP: dict[str, str] = {
    "invoice": "prebuilt-invoice",
    "tax_invoice": "prebuilt-invoice",
    "policy_invoice": "prebuilt-invoice",
    "billing_document": "prebuilt-invoice",
}

DEFAULT_AZURE_MODEL = "prebuilt-invoice"


def resolve_model_id(document_type: str) -> str:
    """Return the Azure model ID for a caller-supplied document type."""
    normalized = (document_type or "invoice").strip().lower()
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

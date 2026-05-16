"""Backward-compatible re-exports; prefer ``apps.ocr.field_mappings``."""

from apps.ocr.field_mappings import (  # noqa: F401
    CURRENCY_FIELDS,
    DATE_FIELDS,
    DEFAULT_AZURE_MODEL,
    DOCUMENT_TYPE_MODEL_MAP,
    FIELD_MAPPING_SCHEMAS,
    GENDER_FIELDS,
    SECONDARY_FIELD_MAPPINGS,
    get_schema_mapping,
    get_secondary_schema_mapping,
    list_supported_schemas,
    resolve_model_id,
    schema_exists,
)

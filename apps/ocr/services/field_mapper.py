"""Maps Azure OCR field names to CRM field names using schema configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from apps.ocr.exceptions import OCRValidationError
from apps.ocr.field_mappings import (
    CURRENCY_FIELDS,
    DATE_FIELDS,
    GENDER_FIELDS,
    PLATE_SOURCE_FIELDS,
    all_crm_fields_for_schema,
    get_schema_mapping,
    get_secondary_schema_mapping,
    schema_exists,
)
from apps.ocr.field_transformers import (
    normalize_text,
    parse_currency,
    parse_date,
    parse_gender,
    parse_plate_source,
)
from apps.ocr.services.azure_ocr_service import OCRResult


@dataclass(frozen=True)
class MappedField:
    """A single CRM field extracted from Azure output."""

    crm_field: str
    value: Any
    confidence: float
    azure_field: str


@dataclass
class MappedFields:
    """Aggregated mapping outcome for a target schema."""

    extracted: list[MappedField] = field(default_factory=list)
    unmapped: list[str] = field(default_factory=list)
    low_confidence: list[MappedField] = field(default_factory=list)

    def extracted_dict(self) -> dict[str, Any]:
        """Return extracted fields as a flat CRM field dictionary."""
        return {item.crm_field: item.value for item in self.extracted}

    def low_confidence_dict(self) -> dict[str, Any]:
        """Return low-confidence fields as a flat CRM field dictionary."""
        return {item.crm_field: item.value for item in self.low_confidence}


def transform_field_value(crm_field: str, value: Any) -> Any:
    """Apply type-specific transformers for a mapped CRM field."""
    if crm_field in DATE_FIELDS:
        return parse_date(value)
    if crm_field in CURRENCY_FIELDS:
        return parse_currency(value)
    if crm_field in GENDER_FIELDS:
        return parse_gender(value)
    if crm_field in PLATE_SOURCE_FIELDS:
        return parse_plate_source(value)
    if isinstance(value, (int, float)):
        return value
    return normalize_text(value)


def map_ocr_fields(ocr_result: OCRResult, target_schema: str) -> MappedFields:
    """Map Azure fields to CRM fields for the given target schema."""
    if not schema_exists(target_schema):
        raise OCRValidationError(
            f"Unknown target_schema: {target_schema}",
            user_message="The requested form schema is not supported.",
        )

    schema_mapping = get_schema_mapping(
        target_schema,
        model_used=ocr_result.model_used,
    )
    secondary_mapping = get_secondary_schema_mapping(
        target_schema,
        model_used=ocr_result.model_used,
    )
    mapped = MappedFields()
    mapped_azure_keys: set[str] = set()

    def append_mapped_field(
        azure_field: str,
        crm_field: str,
        *,
        track_unmapped: bool = True,
    ) -> None:
        """Append a mapped CRM field when the Azure key is present."""
        if azure_field not in ocr_result.raw_fields:
            return
        if any(item.crm_field == crm_field for item in mapped.extracted):
            return
        raw_value = ocr_result.raw_fields[azure_field]
        confidence = float(ocr_result.confidence_scores.get(azure_field, 0.0))
        mapped.extracted.append(
            MappedField(
                crm_field=crm_field,
                value=transform_field_value(crm_field, raw_value),
                confidence=confidence,
                azure_field=azure_field,
            )
        )
        if track_unmapped:
            mapped_azure_keys.add(azure_field)

    for azure_field, crm_field in schema_mapping.items():
        append_mapped_field(azure_field, crm_field)

    for azure_field, crm_field in secondary_mapping.items():
        append_mapped_field(azure_field, crm_field, track_unmapped=False)

    # Parser-enriched keys (e.g. ``name``, ``nationality``) are already CRM names.
    crm_targets = (
        all_crm_fields_for_schema(target_schema)
        | set(schema_mapping.values())
        | set(secondary_mapping.values())
    )
    for crm_field in crm_targets:
        append_mapped_field(crm_field, crm_field, track_unmapped=False)

    for azure_field in ocr_result.raw_fields:
        if azure_field not in mapped_azure_keys:
            mapped.unmapped.append(azure_field)

    return mapped

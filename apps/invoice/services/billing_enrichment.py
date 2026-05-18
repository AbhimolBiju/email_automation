"""Enrich Azure extraction output with billing debit/credit mapper aliases."""

from __future__ import annotations

from typing import Any

from apps.invoice.services.mappers.credit_note_mapper import map_credit_note_to_form
from apps.invoice.services.mappers.debit_note_mapper import map_debit_note_to_form
from apps.invoice.services.parser.router import is_credit_note


def enrich_extracted_fields(
    extracted_fields: dict[str, Any],
    *,
    document_type: str,
    raw_content: str = "",
) -> dict[str, Any]:
    """Merge debit/credit mapper aliases into extracted CRM fields."""
    enriched = dict(extracted_fields)
    credit = is_credit_note(raw_content, document_type)
    mapped = (
        map_credit_note_to_form(enriched)
        if credit
        else map_debit_note_to_form(enriched)
    )

    for key, value in mapped.items():
        if value is None or value == "":
            continue
        enriched[key] = value

    return enriched

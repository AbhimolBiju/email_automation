"""Route parser results to deal_create CRM field dictionaries."""

from __future__ import annotations

from typing import Any

from .driving_license_mapper import map_driving_license_to_deal_create
from .emirates_id_mapper import map_emirates_id_to_deal_create
from .mulkiya_mapper import map_mulkiya_to_deal_create


def map_parser_result_to_deal_create(
    parsed: dict[str, Any],
    *,
    document_type: str,
) -> dict[str, Any]:
    """Map a structured parser payload to flat CRM keys for ``deal_create``."""
    doc_lower = (document_type or parsed.get("document_type") or "").lower()

    if "emirates_id" in doc_lower:
        return map_emirates_id_to_deal_create(parsed)
    if "driving_license" in doc_lower:
        return map_driving_license_to_deal_create(parsed)
    if "mulkiya" in doc_lower:
        return map_mulkiya_to_deal_create(parsed)

    parsed_type = str(parsed.get("document_type") or "").lower()
    if "emirates" in parsed_type:
        return map_emirates_id_to_deal_create(parsed)
    if "driving_license" in parsed_type:
        return map_driving_license_to_deal_create(parsed)
    if "mulkiya" in parsed_type:
        return map_mulkiya_to_deal_create(parsed)

    return {}

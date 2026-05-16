"""Confidence-based splitting of extracted OCR fields."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.conf import settings

from apps.ocr.services.field_mapper import MappedField, MappedFields


@dataclass
class ConfidenceFilterResult:
    """Fields partitioned by confidence threshold."""

    high_confidence: dict[str, Any] = field(default_factory=dict)
    needs_review: dict[str, Any] = field(default_factory=dict)
    confidence_scores: dict[str, float] = field(default_factory=dict)


def get_confidence_threshold() -> float:
    """Read the OCR confidence threshold from Django settings."""
    return float(getattr(settings, "OCR_CONFIDENCE_THRESHOLD", 0.75))


def filter_by_confidence(
    mapped_fields: MappedFields,
    *,
    threshold: float | None = None,
) -> ConfidenceFilterResult:
    """Split mapped fields into high-confidence and needs-review buckets."""
    cutoff = threshold if threshold is not None else get_confidence_threshold()
    result = ConfidenceFilterResult()

    for item in mapped_fields.extracted:
        result.confidence_scores[item.crm_field] = item.confidence
        if item.confidence >= cutoff:
            result.high_confidence[item.crm_field] = item.value
        else:
            result.needs_review[item.crm_field] = item.value

    mapped_fields.low_confidence = [
        item for item in mapped_fields.extracted if item.confidence < cutoff
    ]

    return result

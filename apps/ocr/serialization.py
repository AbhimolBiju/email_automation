"""JSON-safe serialization helpers for OCR payloads."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any


def to_json_safe(value: Any) -> Any:
    """Recursively convert OCR values to JSON-serializable primitives."""
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date().isoformat() if value.tzinfo is None else value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): to_json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_json_safe(item) for item in value]

    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except TypeError:
            pass

    return str(value)


def to_json_safe_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Return a JSON-safe copy of a string-keyed mapping."""
    return {key: to_json_safe(value) for key, value in data.items()}

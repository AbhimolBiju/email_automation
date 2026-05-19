"""Shared helpers for OCR field mappers."""

from __future__ import annotations

from typing import Any


def parser_data(parsed: dict[str, Any]) -> dict[str, Any]:
    """Return the inner ``data`` dict from a parser result."""
    if "data" in parsed and isinstance(parsed["data"], dict):
        return parsed["data"]
    if "values" in parsed and isinstance(parsed["values"], dict):
        return parsed["values"]
    return {}


def set_if_present(
    target: dict[str, Any],
    key: str,
    value: Any,
    *,
    aliases: tuple[str, ...] = (),
) -> None:
    """Set a CRM field and optional Azure alias keys when value is non-empty."""
    if value in (None, ""):
        return
    text = str(value).strip()
    if not text:
        return
    target[key] = text
    for alias in aliases:
        target[alias] = text


def split_full_name(name: str) -> tuple[str, str]:
    """Split a full name into first and last segments."""
    parts = [part for part in name.split() if part]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])

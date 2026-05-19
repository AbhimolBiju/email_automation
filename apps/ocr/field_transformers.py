"""Pure transformation helpers applied after Azure field extraction."""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%d-%m-%Y",
    "%m-%d-%Y",
    "%Y/%m/%d",
    "%d %b %Y",
    "%d %B %Y",
)


def normalize_text(value: Any) -> str:
    """Collapse whitespace and strip surrounding space from text values."""
    if value is None:
        return ""

    if isinstance(value, (date, datetime)):
        return value.date().isoformat() if isinstance(value, datetime) else value.isoformat()

    text = str(value).replace("\n", " ").replace("\r", " ")
    return re.sub(r"\s+", " ", text).strip()


def parse_date(value: Any) -> str:
    """Parse a date-like value and return an ISO date string (YYYY-MM-DD)."""
    if value is None or value == "":
        return ""

    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()

    text = normalize_text(value)
    if not text:
        return ""

    try:
        from dateutil import parser as date_parser

        return date_parser.parse(text, dayfirst=True).date().isoformat()
    except Exception:
        pass

    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue

    return text


def parse_plate_source(value: Any) -> str:
    """Translate Arabic place-of-issue text and normalize plate source labels."""
    from apps.ocr.plate_utils import normalize_plate_source

    text = normalize_text(value)
    if not text:
        return ""
    return normalize_plate_source(text)


def parse_gender(value: Any) -> str:
    """Map Azure ``Sex`` values (M/F) to form labels Male/Female."""
    text = normalize_text(value).upper()
    if text in {"M", "MALE"}:
        return "Male"
    if text in {"F", "FEMALE"}:
        return "Female"
    return normalize_text(value)


def parse_currency(value: Any) -> Decimal:
    """Parse a currency-like value and return a ``Decimal`` amount."""
    if value is None or value == "":
        return Decimal("0")

    if isinstance(value, Decimal):
        return value

    if isinstance(value, (int, float)):
        return Decimal(str(value))

    if isinstance(value, dict):
        for key in ("amount", "value", "total"):
            if key in value:
                return parse_currency(value[key])
        return Decimal("0")

    text = normalize_text(value)
    if not text:
        return Decimal("0")

    cleaned = re.sub(r"[^\d.,\-]", "", text)
    if not cleaned:
        return Decimal("0")

    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        parts = cleaned.split(",")
        cleaned = (
            parts[0].replace(".", "") + "." + parts[1]
            if len(parts) == 2 and len(parts[1]) <= 2
            else cleaned.replace(",", "")
        )

    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return Decimal("0")

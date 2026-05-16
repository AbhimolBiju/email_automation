"""Parse UAE driving license OCR text for fields missing from Azure structured output."""

from __future__ import annotations

import re
from typing import Any

from documents.ocr_parser import extract_labeled_value, normalize_space, parse_date

DATE_TOKEN_RE = re.compile(r"\b\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}\b")

ISSUE_DATE_FIELD_KEYS: tuple[str, ...] = (
    "DateOfIssue",
    "date_of_issue",
    "issue_date",
    "license_from_date",
    "valid_from",
)

EXPIRY_DATE_FIELD_KEYS: tuple[str, ...] = (
    "DateOfExpiration",
    "date_of_expiration",
    "expiry_date",
    "license_to_date",
    "license_expiry_date",
    "valid_until",
    "valid_to",
)

ISSUE_DATE_LABELS: tuple[str, ...] = (
    "issue date",
    "date of issue",
    "issued on",
    "valid from",
    "تاريخ الإصدار",
    "تاريخ الاصدار",
)

EXPIRY_DATE_LABELS: tuple[str, ...] = (
    "expiry date",
    "date of expiry",
    "date of expiration",
    "expires",
    "valid until",
    "valid to",
    "تاريخ الانتهاء",
    "تاريخ انتهاء",
)

ISSUE_DATE_EMBEDDED_RE = re.compile(
    r"^(?:Issue\s*Date|Date\s*of\s*Issue|Issued\s*On)\s*[:.\-]?\s*(.+)$",
    re.IGNORECASE,
)
EXPIRY_DATE_EMBEDDED_RE = re.compile(
    r"^(?:Expiry\s*Date|Date\s*of\s*Expiry|Date\s*of\s*Expiration|Expires|Valid\s*Until|Valid\s*To)\s*[:.\-]?\s*(.+)$",
    re.IGNORECASE,
)

LICENSE_FIELD_KEYS: tuple[str, ...] = (
    "DocumentNumber",
    "LicenseNumber",
    "license_no",
    "licence_no",
    "license_number",
    "Number",
)

LICENSE_EMBEDDED_RE = re.compile(
    r"^(?:License|Licence)\s*(?:No|Number)?\s*[:.\-]?\s*(.+)$",
    re.IGNORECASE,
)
LICENSE_LABEL_RE = re.compile(
    r"^(?:License|Licence)\s*(?:No|Number)?\s*[:.\-]?\s*(.*)$",
    re.IGNORECASE,
)
LICENSE_INLINE_RE = re.compile(
    r"\b(?:License|Licence)\s*(?:No|Number)?\s*[:.\-]\s*([A-Z0-9/-]{4,20})",
    re.IGNORECASE,
)
EMIRATES_ID_RE = re.compile(r"^784[-\s]?\d{4}[-\s]?\d{7}[-\s]?\d$", re.IGNORECASE)


def _lines(text: str) -> list[str]:
    """Return normalized non-empty lines from OCR text."""
    return [normalize_space(line) for line in text.splitlines() if normalize_space(line)]


def strip_license_label(value: str) -> str:
    """Remove duplicated license number label text from OCR/Azure values."""
    cleaned = normalize_space(value)
    if not cleaned:
        return ""

    match = LICENSE_EMBEDDED_RE.match(cleaned)
    if match:
        return normalize_space(match.group(1)).strip(" .,:;")

    return cleaned.strip(" .,:;")


def _looks_like_emirates_id(value: str) -> bool:
    """Return True when the value matches a UAE Emirates ID number."""
    compact = re.sub(r"\s+", "", value)
    return bool(EMIRATES_ID_RE.match(compact))


def normalize_license_number(value: str) -> str:
    """Normalize license number text for CRM storage."""
    cleaned = strip_license_label(value)
    if not cleaned:
        return ""

    if _looks_like_emirates_id(cleaned):
        return ""

    compact = re.sub(r"\s+", "", cleaned)
    if re.fullmatch(r"[A-Z0-9/-]+", compact, re.IGNORECASE):
        return compact.upper()

    token_match = re.search(r"[A-Z0-9][A-Z0-9/-]{3,19}", cleaned, re.IGNORECASE)
    if token_match:
        return token_match.group(0).upper()

    return cleaned.upper()


def _string_field_value(value: Any, *, strip_license: bool = True) -> str:
    """Return a single string from an Azure field value."""
    if isinstance(value, str):
        return strip_license_label(value) if strip_license else normalize_space(value)
    if isinstance(value, dict):
        for key in ("content", "value", "name", "code"):
            nested = value.get(key)
            if isinstance(nested, str) and nested.strip():
                return (
                    strip_license_label(nested)
                    if strip_license
                    else normalize_space(nested)
                )
    for attr in ("content", "value", "name", "code"):
        nested = getattr(value, attr, None)
        if isinstance(nested, str) and nested.strip():
            return (
                strip_license_label(nested) if strip_license else normalize_space(nested)
            )
    return ""


def _parse_date_value(value: str) -> str | None:
    """Parse a date string to ISO format (YYYY-MM-DD)."""
    cleaned = normalize_space(value).strip(" .,:;")
    if not cleaned:
        return None

    token_match = DATE_TOKEN_RE.search(cleaned)
    if token_match:
        return parse_date(token_match.group(0))

    return parse_date(cleaned)


def _date_from_fields(
    existing_fields: dict[str, Any],
    field_keys: tuple[str, ...],
) -> str | None:
    """Read a date from Azure structured fields."""
    for key in field_keys:
        if key not in existing_fields:
            continue
        raw = _string_field_value(existing_fields[key], strip_license=False)
        if raw:
            parsed = _parse_date_value(raw)
            if parsed:
                return parsed
    return None


def _date_from_label_lines(
    lines: list[str],
    *,
    embedded_pattern: re.Pattern[str],
    label_aliases: tuple[str, ...],
) -> str | None:
    """Extract a date from labeled lines in OCR content."""
    for index, line in enumerate(lines):
        embedded = embedded_pattern.match(line)
        if embedded:
            remainder = normalize_space(embedded.group(1))
            if remainder:
                parsed = _parse_date_value(remainder)
                if parsed:
                    return parsed

        lowered = line.lower()
        if any(alias in lowered for alias in label_aliases):
            inline = re.split(r"[:\-]", line, maxsplit=1)
            if len(inline) == 2 and normalize_space(inline[1]):
                parsed = _parse_date_value(inline[1])
                if parsed:
                    return parsed
            for candidate in lines[index + 1 : index + 4]:
                parsed = _parse_date_value(candidate)
                if parsed:
                    return parsed

    labeled = extract_labeled_value(lines, label_aliases)
    if labeled:
        return _parse_date_value(labeled)

    return None


def extract_license_dates_from_license_front(
    text: str,
    *,
    existing_fields: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Extract license issue and expiry dates from driving license front OCR."""
    existing_fields = existing_fields or {}
    lines = _lines(text)
    data: dict[str, str] = {}

    issue = _date_from_fields(existing_fields, ISSUE_DATE_FIELD_KEYS)
    if not issue:
        issue = _date_from_label_lines(
            lines,
            embedded_pattern=ISSUE_DATE_EMBEDDED_RE,
            label_aliases=ISSUE_DATE_LABELS,
        )
    if issue:
        data["license_from_date"] = issue

    expiry = _date_from_fields(existing_fields, EXPIRY_DATE_FIELD_KEYS)
    if not expiry:
        expiry = _date_from_label_lines(
            lines,
            embedded_pattern=EXPIRY_DATE_EMBEDDED_RE,
            label_aliases=EXPIRY_DATE_LABELS,
        )
    if expiry:
        data["license_to_date"] = expiry

    return data


def _license_from_label(lines: list[str]) -> str:
    """Read license number from License No label lines in OCR content."""
    for index, line in enumerate(lines):
        match = LICENSE_LABEL_RE.match(line)
        if not match:
            continue

        inline = strip_license_label(match.group(1))
        if inline:
            return inline

        for candidate in lines[index + 1 : index + 4]:
            candidate = normalize_space(candidate)
            if candidate and len(candidate) <= 24:
                return candidate

    inline_match = LICENSE_INLINE_RE.search("\n".join(lines))
    if inline_match:
        return normalize_space(inline_match.group(1))

    return ""


def extract_license_number_from_license_front(
    text: str,
    *,
    existing_fields: dict[str, Any] | None = None,
) -> str:
    """Extract license number from driving license front OCR output."""
    existing_fields = existing_fields or {}

    for key in LICENSE_FIELD_KEYS:
        if key not in existing_fields:
            continue
        raw = _string_field_value(existing_fields[key])
        if raw:
            normalized = normalize_license_number(raw)
            if normalized:
                return normalized

    labeled = _license_from_label(_lines(text))
    if labeled:
        return normalize_license_number(labeled)

    return ""


def parse_driving_license_document(
    text: str,
    *,
    existing_fields: dict[str, Any] | None = None,
    document_type: str = "",
) -> dict[str, Any]:
    """Extract driving license fields from OCR output."""
    data: dict[str, Any] = {}
    doc_lower = (document_type or "").lower()
    if "driving_license_front" not in doc_lower and doc_lower != "driving_license":
        return data

    license_no = extract_license_number_from_license_front(
        text,
        existing_fields=existing_fields,
    )
    if license_no:
        data["license_no"] = license_no

    data.update(
        extract_license_dates_from_license_front(
            text,
            existing_fields=existing_fields,
        )
    )
    return data

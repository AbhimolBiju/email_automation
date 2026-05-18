"""Route OCR text to insurer-specific credit/debit note parsers."""

from __future__ import annotations

import logging
from typing import Any

from apps.invoice.services.parser.adamjee_credit_note_parser import parse_adamjee_credit_note
from apps.invoice.services.parser.adamjee_debit_note_parser import parse_adamjee_debit_note
from apps.invoice.services.parser.al_sagr_credit_note_parser import parse_al_sagr_credit_note
from apps.invoice.services.parser.al_sagr_debit_note_parser import parse_al_sagr_debit_note
from apps.invoice.services.parser.qic_credit_note_parser import parse_qic_credit_note
from apps.invoice.services.parser.qic_debit_note_parser import parse_qic_debit_note

logger = logging.getLogger(__name__)

InsurerKey = str  # qic | al_sagr | adamjee


def detect_insurer(text: str) -> InsurerKey | None:
    """Detect insurer from OCR content."""
    upper = f" {text.upper()} "

    if any(
        token in upper
        for token in (
            " QIC ",
            "QATAR INSURANCE",
            "QATAR INSURANCE COMPANY",
        )
    ):
        return "qic"

    if any(token in upper for token in ("AL SAGR", "ASNIC", "AL SAGR NATIONAL")):
        return "al_sagr"

    if "ADAMJEE" in upper:
        return "adamjee"

    return None


def is_credit_note(text: str, document_type: str) -> bool:
    """Return True when the upload is a credit note."""
    doc = (document_type or "").strip().lower()
    if "credit" in doc or doc == "tax_invoice":
        return True

    upper = text.upper()
    return any(
        phrase in upper
        for phrase in (
            "CREDIT NOTE",
            "TAX INVOICE RAISED BY BUYER",
            "CREDITED YOUR ACCOUNT",
            "WE HAVE CREDITED",
        )
    )


def _coerce_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    return value


def normalize_parser_output(raw: dict[str, Any]) -> dict[str, Any]:
    """Map insurer parser keys to CRM keys consumed by field_mapper / frontend."""
    if not raw:
        return {}

    normalized: dict[str, Any] = {}

    for key, value in raw.items():
        coerced = _coerce_value(value)
        if coerced is not None:
            normalized[key] = coerced

    if normalized.get("period_from") and not normalized.get("policy_start_date"):
        normalized["policy_start_date"] = normalized["period_from"]

    if normalized.get("period_to") and not normalized.get("policy_end_date"):
        normalized["policy_end_date"] = normalized["period_to"]

    total = (
        normalized.get("total_amount")
        or normalized.get("total_premium")
        or normalized.get("total")
    )
    if total is not None:
        normalized["total_amount"] = total
        normalized["premium_amount"] = total

    if normalized.get("invoice_number") and not normalized.get("invoice_no"):
        normalized["invoice_no"] = normalized["invoice_number"]

    insurer = normalized.get("insurer_name")
    if insurer:
        normalized["vendor_name"] = insurer

    return normalized


def parse_insurance_document(
    text: str,
    *,
    document_type: str = "",
    tables: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Parse OCR text using the matching insurer credit/debit parser.

    Returns CRM-oriented field dict (may be empty when insurer is unknown).
    """
    if not text.strip():
        return {}

    insurer = detect_insurer(text)
    if insurer is None:
        logger.debug("No insurer-specific parser matched document_type=%s", document_type)
        return {}

    credit = is_credit_note(text, document_type)

    try:
        if insurer == "qic":
            raw = (
                parse_qic_credit_note(text)
                if credit
                else parse_qic_debit_note(text, tables=tables)
            )
        elif insurer == "al_sagr":
            raw = (
                parse_al_sagr_credit_note(text)
                if credit
                else parse_al_sagr_debit_note(text, tables=tables)
            )
        elif insurer == "adamjee":
            raw = (
                parse_adamjee_credit_note(text)
                if credit
                else parse_adamjee_debit_note(text, tables=tables)
            )
        else:
            raw = {}
    except Exception:
        logger.exception(
            "Insurer parser failed insurer=%s credit=%s document_type=%s",
            insurer,
            credit,
            document_type,
        )
        return {}

    parsed = normalize_parser_output(raw)
    if parsed:
        parsed["_parser_meta"] = {
            "insurer": insurer,
            "is_credit_note": credit,
        }
    return parsed

"""Route OCR text to insurer-specific credit/debit note parsers."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from apps.invoice.services.parser.adamjee_credit_note_parser import parse_adamjee_credit_note
from apps.invoice.services.parser.adamjee_debit_note_parser import parse_adamjee_debit_note
from apps.invoice.services.parser.al_sagr_credit_note_parser import parse_al_sagr_credit_note
from apps.invoice.services.parser.al_sagr_debit_note_parser import parse_al_sagr_debit_note
from apps.invoice.services.parser.alliance_credit_note_parser import parse_alliance_credit_note
from apps.invoice.services.parser.alliance_debit_note_parser import parse_alliance_debit_note
from apps.invoice.services.parser.arabia_credit_note_parser import parse_arabia_credit_note
from apps.invoice.services.parser.arabia_debit_note_parser import parse_arabia_debit_note
from apps.invoice.services.parser.commission_utils import resolve_commission_fields
from apps.invoice.services.parser.dni_credit_note_parser import parse_dni_credit_note
from apps.invoice.services.parser.dni_debit_note_parser import parse_dni_debit_note
from apps.invoice.services.parser.fidelity_credit_note_parser import parse_fidelity_credit_note
from apps.invoice.services.parser.fidelity_debit_note_parser import parse_fidelity_debit_note
from apps.invoice.services.parser.methaq_credit_note_parser import parse_methaq_credit_note
from apps.invoice.services.parser.methaq_debit_note_parser import parse_methaq_debit_note
from apps.invoice.services.parser.nia_credit_note_parser import parse_nia_credit_note
from apps.invoice.services.parser.nia_debit_note_parser import parse_nia_debit_note
from apps.invoice.services.parser.qic_credit_note_parser import parse_qic_credit_note
from apps.invoice.services.parser.qic_debit_note_parser import parse_qic_debit_note
from apps.invoice.services.parser.rak_credit_note_parser import parse_rak_credit_note
from apps.invoice.services.parser.rak_debit_note_parser import parse_rak_debit_note
from apps.invoice.services.parser.sharjah_credit_note_parser import parse_sharjah_credit_note
from apps.invoice.services.parser.sharjah_debit_note_parser import parse_sharjah_debit_note
from apps.invoice.services.parser.watania_credit_note_parser import parse_watania_credit_note
from apps.invoice.services.parser.watania_debit_note_parser import parse_watania_debit_note

logger = logging.getLogger(__name__)

InsurerKey = str

# Order matters: more specific tokens before generic substrings.
_INSURER_DETECTORS: list[tuple[InsurerKey, tuple[str, ...]]] = [
    (
        "qic",
        (" QIC ", "QATAR INSURANCE", "QATAR INSURANCE COMPANY"),
    ),
    ("al_sagr", ("AL SAGR", "ASNIC", "AL SAGR NATIONAL")),
    ("adamjee", ("ADAMJEE",)),
    ("watania", ("WATANIA TAKAFUL", "WATANIA")),
    ("sharjah", ("SHARJAH INSURANCE",)),
    ("rak", ("RAK INSURANCE",)),
    (
        "nia",
        (
            "THE NEW INDIA ASSURANCE",
            "NEW INDIA ASSURANCE",
            " NIA INSURANCE",
        ),
    ),
    ("methaq", ("METHAQ TAKAFUL", "METHAQ")),
    (
        "fidelity",
        ("UNITED FIDELITY INSURANCE", "FIDELITY"),
    ),
    ("dni", ("DUBAI NATIONAL INSURANCE", " DNI ")),
    ("arabia", ("ARABIA INSURANCE",)),
    ("alliance", ("ALLIANCE INSURANCE", "ALLIANCE")),
]

_CREDIT_PARSERS: dict[InsurerKey, Callable[[str], dict[str, Any]]] = {
    "qic": parse_qic_credit_note,
    "al_sagr": parse_al_sagr_credit_note,
    "adamjee": parse_adamjee_credit_note,
    "alliance": parse_alliance_credit_note,
    "arabia": parse_arabia_credit_note,
    "dni": parse_dni_credit_note,
    "fidelity": parse_fidelity_credit_note,
    "methaq": parse_methaq_credit_note,
    "nia": parse_nia_credit_note,
    "rak": parse_rak_credit_note,
    "sharjah": parse_sharjah_credit_note,
    "watania": parse_watania_credit_note,
}

_DEBIT_PARSERS: dict[InsurerKey, Callable[..., dict[str, Any]]] = {
    "qic": parse_qic_debit_note,
    "al_sagr": parse_al_sagr_debit_note,
    "adamjee": parse_adamjee_debit_note,
    "alliance": parse_alliance_debit_note,
    "arabia": parse_arabia_debit_note,
    "dni": parse_dni_debit_note,
    "fidelity": parse_fidelity_debit_note,
    "methaq": parse_methaq_debit_note,
    "nia": parse_nia_debit_note,
    "rak": parse_rak_debit_note,
    "sharjah": parse_sharjah_debit_note,
    "watania": parse_watania_debit_note,
}


def detect_insurer(text: str) -> InsurerKey | None:
    """Detect insurer from OCR content."""
    upper = f" {text.upper()} "

    for insurer_key, tokens in _INSURER_DETECTORS:
        if any(token in upper for token in tokens):
            return insurer_key

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

    if normalized.get("company_name") and not normalized.get("insurer_name"):
        normalized["insurer_name"] = normalized["company_name"]

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

    net_premium = normalized.get("net_premium")
    vat_amount = normalized.get("vat_amount")
    total_amount = normalized.get("total_amount")

    if net_premium is not None:
        normalized.setdefault("customer_net_premium", net_premium)
    if vat_amount is not None:
        normalized.setdefault("customer_vat_amount", vat_amount)
    if total_amount is not None:
        normalized.setdefault("customer_total_premium", total_amount)

    if normalized.get("tax_amount") and not normalized.get("vat_amount"):
        normalized["vat_amount"] = normalized["tax_amount"]

    normalized = resolve_commission_fields(normalized)

    commission_amount = normalized.get("commission_amount")
    if commission_amount and not normalized.get("vat_amount"):
        try:
            commission = float(str(commission_amount).replace(",", ""))
            normalized["vat_amount"] = round(commission * 0.05, 2)
        except (TypeError, ValueError):
            pass

    return normalized


def _run_parser(
    insurer: InsurerKey,
    *,
    credit: bool,
    text: str,
    tables: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    if credit:
        parser_fn = _CREDIT_PARSERS.get(insurer)
        return parser_fn(text) if parser_fn else {}

    parser_fn = _DEBIT_PARSERS.get(insurer)
    return parser_fn(text, tables=tables) if parser_fn else {}


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
        raw = _run_parser(insurer, credit=credit, text=text, tables=tables)
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

"""Route parsed invoice fields to insurer-specific validators."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from apps.invoice.services.parser.router import detect_insurer, is_credit_note
from apps.invoice.services.validator.adamjee_credit_note_validator import (
    validate_adamjee_credit_note,
)
from apps.invoice.services.validator.adamjee_debit_note_validator import (
    validate_adamjee_debit_note,
)
from apps.invoice.services.validator.al_sagr_credit_note_validator import (
    validate_al_sagr_credit_note,
)
from apps.invoice.services.validator.al_sagr_debit_note_validator import (
    validate_al_sagr_debit_note,
)
from apps.invoice.services.validator.alliance_credit_note_validator import (
    validate_alliance_credit_note,
)
from apps.invoice.services.validator.alliance_debit_note_validator import (
    validate_alliance_debit_note,
)
from apps.invoice.services.validator.arabia_credit_note_validator import (
    validate_arabia_credit_note,
)
from apps.invoice.services.validator.arabia_debit_note_validator import (
    validate_arabia_debit_note,
)
from apps.invoice.services.validator.dni_credit_note_validator import (
    validate_dni_credit_note,
)
from apps.invoice.services.validator.dni_debit_note_validator import (
    validate_dni_debit_note,
)
from apps.invoice.services.validator.fidelity_credit_note_validator import (
    validate_fidelity_credit_note,
)
from apps.invoice.services.validator.fidelity_debit_note_validator import (
    validate_fidelity_debit_note,
)
from apps.invoice.services.validator.methaq_credit_note_validator import (
    validate_methaq_credit_note,
)
from apps.invoice.services.validator.methaq_debit_note_validator import (
    validate_methaq_debit_note,
)
from apps.invoice.services.validator.nia_credit_note_validator import (
    validate_nia_credit_note,
)
from apps.invoice.services.validator.nia_debit_note_validator import (
    validate_nia_debit_note,
)
from apps.invoice.services.validator.qic_credit_note_validator import (
    validate_qic_credit_note,
)
from apps.invoice.services.validator.qic_debit_note_validator import (
    validate_qic_debit_note,
)
from apps.invoice.services.validator.rak_credit_note_validator import (
    validate_rak_credit_note,
)
from apps.invoice.services.validator.rak_debit_note_validator import (
    validate_rak_debit_note,
)
from apps.invoice.services.validator.sharjah_credit_note_validator import (
    validate_sharjah_credit_note,
)
from apps.invoice.services.validator.sharjah_debit_note_validator import (
    validate_sharjah_debit_note,
)
from apps.invoice.services.validator.watania_credit_note_validator import (
    validate_watania_credit_note,
)
from apps.invoice.services.validator.watania_debit_note_validator import (
    validate_watania_debit_note,
)

logger = logging.getLogger(__name__)

ValidationResult = dict[str, Any]
ValidatorFn = Callable[[dict[str, Any]], ValidationResult]

_CREDIT_VALIDATORS: dict[str, ValidatorFn] = {
    "qic": validate_qic_credit_note,
    "al_sagr": validate_al_sagr_credit_note,
    "adamjee": validate_adamjee_credit_note,
    "alliance": validate_alliance_credit_note,
    "arabia": validate_arabia_credit_note,
    "dni": validate_dni_credit_note,
    "fidelity": validate_fidelity_credit_note,
    "methaq": validate_methaq_credit_note,
    "nia": validate_nia_credit_note,
    "rak": validate_rak_credit_note,
    "sharjah": validate_sharjah_credit_note,
    "watania": validate_watania_credit_note,
}

_DEBIT_VALIDATORS: dict[str, ValidatorFn] = {
    "qic": validate_qic_debit_note,
    "al_sagr": validate_al_sagr_debit_note,
    "adamjee": validate_adamjee_debit_note,
    "alliance": validate_alliance_debit_note,
    "arabia": validate_arabia_debit_note,
    "dni": validate_dni_debit_note,
    "fidelity": validate_fidelity_debit_note,
    "methaq": validate_methaq_debit_note,
    "nia": validate_nia_debit_note,
    "rak": validate_rak_debit_note,
    "sharjah": validate_sharjah_debit_note,
    "watania": validate_watania_debit_note,
}


def validate_insurance_document(
    parsed_data: dict[str, Any],
    *,
    raw_content: str = "",
    document_type: str = "",
    insurer: str | None = None,
    is_credit: bool | None = None,
) -> ValidationResult | None:
    """
    Run insurer-specific validation when an insurer can be resolved.

    Returns None when no insurer-specific validator applies.
    """
    meta = parsed_data.get("_parser_meta") or {}
    resolved_insurer = insurer or meta.get("insurer") or detect_insurer(raw_content)
    if not resolved_insurer:
        return None

    credit = (
        is_credit
        if is_credit is not None
        else meta.get("is_credit_note", is_credit_note(raw_content, document_type))
    )

    validator_fn = (
        _CREDIT_VALIDATORS.get(resolved_insurer)
        if credit
        else _DEBIT_VALIDATORS.get(resolved_insurer)
    )
    if validator_fn is None:
        return None

    try:
        result = validator_fn(parsed_data)
    except Exception:
        logger.exception(
            "Insurer validator failed insurer=%s credit=%s document_type=%s",
            resolved_insurer,
            credit,
            document_type,
        )
        return {
            "is_valid": False,
            "missing_fields": [],
            "message": "Validation failed due to an internal error.",
            "insurer": resolved_insurer,
            "is_credit_note": credit,
        }

    return {
        **result,
        "insurer": resolved_insurer,
        "is_credit_note": credit,
    }


def apply_validation_to_review_fields(
    extracted_fields: dict[str, Any],
    needs_review_fields: dict[str, Any],
    validation: ValidationResult | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Merge validation outcome into extracted and needs-review payloads."""
    if not validation:
        return extracted_fields, needs_review_fields

    enriched = dict(extracted_fields)
    enriched["_validation"] = {
        "is_valid": validation.get("is_valid"),
        "missing_fields": validation.get("missing_fields", []),
        "message": validation.get("message"),
        "insurer": validation.get("insurer"),
        "is_credit_note": validation.get("is_credit_note"),
    }

    if validation.get("is_valid"):
        return enriched, needs_review_fields

    review = dict(needs_review_fields)
    for field in validation.get("missing_fields", []):
        review[field] = enriched.get(field)

    return enriched, review

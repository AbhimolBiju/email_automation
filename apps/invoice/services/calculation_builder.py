"""Build billing calculation grid values from debit + credit OCR fields."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any


def _to_decimal(value: Any, default: Decimal | None = None) -> Decimal:
    if value is None or value == "":
        return default if default is not None else Decimal("0")
    try:
        return Decimal(str(value).replace(",", "")).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
    except Exception:
        return default if default is not None else Decimal("0")


def _decimal_str(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "f")


def _pick(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        val = data.get(key)
        if val is not None and val != "":
            return val
    return None


def build_calculation_from_documents(
    debit_fields: dict[str, Any] | None,
    credit_fields: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Mirror legacy ``calculate_invoice_ocr`` grid logic.

    Debit note → customer row (net premium, VAT, total, net due).
    Credit note → insurance company commission %, commission amount, VAT.
    Insurance company net due = customer net due − (commission + VAT).
    """
    debit = debit_fields or {}
    credit = credit_fields or {}

    cus_net_premium = _to_decimal(
        _pick(
            debit,
            "customer_net_premium",
            "net_premium",
        ),
    )
    cus_vat_amount = _to_decimal(
        _pick(
            debit,
            "customer_vat_amount",
            "vat_amount",
            "tax_amount",
        ),
    )
    cus_total_premium = _to_decimal(
        _pick(
            debit,
            "customer_total_premium",
            "total_amount",
            "premium_amount",
            "total",
        ),
    )
    if cus_total_premium == Decimal("0") and cus_net_premium and cus_vat_amount:
        cus_total_premium = (cus_net_premium + cus_vat_amount).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

    cus_net_due = (cus_net_premium + cus_vat_amount).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )

    ic_commission_pct = _to_decimal(
        _pick(
            credit,
            "commission_percentage",
            "own_damage_commission_percentage",
            "third_party_commission_percentage",
            "brokerage_percentage",
        ),
    )
    ic_commission_amount = _to_decimal(
        _pick(
            credit,
            "commission_amount",
            "own_damage_commission_amount",
            "third_party_commission_amount",
            "brokerage_amount",
        ),
    )
    ic_vat_amount = _to_decimal(
        _pick(
            credit,
            "vat_amount",
            "tax_amount",
        ),
    )

    ic_net_premium = cus_net_premium
    ic_charges = Decimal("0.00")
    ic_total_premium = cus_total_premium
    ic_net_due = (cus_net_due - (ic_commission_amount + ic_vat_amount)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )

    return {
        "customer": {
            "net_premium": _decimal_str(cus_net_premium),
            "vat_amount": _decimal_str(cus_vat_amount),
            "charges": _decimal_str(Decimal("0.00")),
            "total_premium": _decimal_str(cus_total_premium),
            "net_due": _decimal_str(cus_net_due),
            "commission_percent": "",
            "commission_amount": "",
            "discount_percent": "",
            "discount_amount": "",
            "fees": "",
        },
        "insurance_company": {
            "net_premium": _decimal_str(ic_net_premium),
            "charges": _decimal_str(ic_charges),
            "total_premium": _decimal_str(ic_total_premium),
            "commission_percent": _decimal_str(ic_commission_pct),
            "commission_amount": _decimal_str(ic_commission_amount),
            "vat_amount": _decimal_str(ic_vat_amount),
            "net_due": _decimal_str(ic_net_due),
            "discount_percent": "",
            "discount_amount": "",
            "fees": "",
        },
        "direct_paid_amount": _decimal_str(cus_total_premium),
        "customer_calculation": {
            "step1_total_premium": (
                f"{_decimal_str(cus_net_premium)} + {_decimal_str(cus_vat_amount)} "
                f"= {_decimal_str(cus_total_premium)}"
            ),
        },
        "insurance_company_calculation": {
            "step1_total_premium": (
                f"{_decimal_str(ic_net_premium)} + {_decimal_str(ic_charges)} "
                f"= {_decimal_str(ic_total_premium)}"
            ),
            "step2_commission_percentage": f"OCR Commission % = {_decimal_str(ic_commission_pct)}%",
            "step3_commission_amount": (
                f"OCR Commission Amount = {_decimal_str(ic_commission_amount)}"
            ),
            "step4_vat_amount": f"OCR VAT Amount = {_decimal_str(ic_vat_amount)}",
            "step5_net_due": (
                f"{_decimal_str(cus_net_due)} - "
                f"({_decimal_str(ic_commission_amount)} + {_decimal_str(ic_vat_amount)}) "
                f"= {_decimal_str(ic_net_due)}"
            ),
        },
    }

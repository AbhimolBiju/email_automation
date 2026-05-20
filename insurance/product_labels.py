"""Human-readable product labels for deals and quote batches."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from deals.models import Deal
    from leads.models import Lead


def lead_product_type_label(lead: Lead | None) -> str:
    """Display label from Create Lead ``product_type`` (Motor, General, Medical)."""
    if lead is None:
        return "Motor"

    product_type = getattr(lead, "product_type", None)
    if not product_type:
        return "Motor"

    try:
        display = lead.get_product_type_display()
        if display:
            return str(display)
    except Exception:
        pass

    return str(product_type).replace("_", " ").strip().title() or "Motor"


def deal_product_type_label(deal: Deal) -> str:
    """Product column label for a motor deal (from linked lead product type)."""
    lead = getattr(deal, "lead", None)
    return lead_product_type_label(lead)

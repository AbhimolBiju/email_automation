"""Resolve commission_amount / commission_percentage from parser output variants."""

from __future__ import annotations

import re
from typing import Any


def _parse_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", "").strip().replace("%", "")
    if not text:
        return None
    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group())
    except ValueError:
        return None


def _format_amount(value: float) -> str | float:
    rounded = round(value, 2)
    if rounded == int(rounded):
        return int(rounded) if rounded == int(rounded) else rounded
    return rounded


def resolve_commission_fields(data: dict[str, Any]) -> dict[str, Any]:
    """
    Ensure top-level commission_amount and commission_percentage are set.

    Uses commission_items, own_damage_* / third_party_* splits, and common aliases.
    """
    if not data:
        return data

    amount = _parse_number(data.get("commission_amount"))
    percentage = data.get("commission_percentage")
    if percentage is not None:
        percentage = str(percentage).replace("%", "").strip() or None

    items = data.get("commission_items")
    if isinstance(items, list) and items:
        items_total = 0.0
        items_pct: str | None = None
        for item in items:
            if not isinstance(item, dict):
                continue
            item_amount = _parse_number(item.get("commission_amount"))
            if item_amount:
                items_total += item_amount
            item_pct = item.get("commission_percentage")
            if item_pct and items_pct is None:
                items_pct = str(item_pct).replace("%", "").strip()

        if items_total and amount is None:
            amount = items_total
        if items_pct and not percentage:
            percentage = items_pct

    od_amount = _parse_number(data.get("own_damage_commission_amount"))
    tp_amount = _parse_number(data.get("third_party_commission_amount"))
    if od_amount is not None or tp_amount is not None:
        split_total = (od_amount or 0) + (tp_amount or 0)
        if split_total and amount is None:
            amount = split_total
        if not percentage:
            percentage = (
                data.get("own_damage_commission_percentage")
                or data.get("third_party_commission_percentage")
            )
            if percentage is not None:
                percentage = str(percentage).replace("%", "").strip() or None

    for amount_key in ("brokerage_amount", "broker_commission_amount"):
        if amount is None:
            parsed = _parse_number(data.get(amount_key))
            if parsed is not None:
                amount = parsed

    for pct_key in ("brokerage_percentage", "broker_commission_percentage", "commission_percent"):
        if not percentage:
            raw = data.get(pct_key)
            if raw is not None and str(raw).strip():
                percentage = str(raw).replace("%", "").strip()

    if amount is not None:
        data["commission_amount"] = _format_amount(amount)
    if percentage:
        data["commission_percentage"] = percentage

    return data

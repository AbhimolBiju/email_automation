"""Map Emirates ID parser output to deal_create CRM fields."""

from __future__ import annotations

from typing import Any

from apps.ocr.field_transformers import parse_date, parse_gender

from .base import parser_data, set_if_present, split_full_name


def map_emirates_id_to_deal_create(parsed: dict[str, Any]) -> dict[str, Any]:
    data = parser_data(parsed)
    mapped: dict[str, Any] = {}

    eid = data.get("emirates_id_number") or data.get("emirates_id")
    if eid:
        compact = str(eid).replace(" ", "").replace("-", "")
        set_if_present(
            mapped,
            "emirates_id",
            eid,
            aliases=("DocumentNumber", "id_number", "IDNumber"),
        )
        if compact.isdigit() and len(compact) >= 15:
            formatted = compact
            if len(compact) == 15:
                formatted = (
                    f"{compact[:3]}-{compact[3:7]}-{compact[7:14]}-{compact[14]}"
                )
            mapped["emirates_id"] = formatted

    name = data.get("name")
    if name:
        first, last = split_full_name(str(name))
        set_if_present(mapped, "first_name", first)
        set_if_present(mapped, "last_name", last)
        set_if_present(mapped, "name", str(name).strip())

    dob = parse_date(data.get("date_of_birth"))
    set_if_present(mapped, "date_of_birth", dob, aliases=("dob",))

    expiry = parse_date(data.get("expiry_date"))
    set_if_present(
        mapped,
        "id_expiry_date",
        expiry,
        aliases=("expiry_date", "DateOfExpiration"),
    )

    nationality = data.get("nationality")
    set_if_present(mapped, "nationality", nationality, aliases=("Nationality",))

    gender = parse_gender(data.get("sex") or data.get("gender"))
    set_if_present(mapped, "gender", gender, aliases=("Sex",))

    issuing_place = data.get("issuing_place")
    set_if_present(
        mapped,
        "emirate",
        issuing_place,
        aliases=("IssuingPlace", "issuing_place", "region"),
    )

    return mapped

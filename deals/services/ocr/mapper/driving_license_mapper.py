"""Map driving license parser output to deal_create CRM fields."""

from __future__ import annotations

from typing import Any

from apps.ocr.field_transformers import parse_date

from .base import parser_data, set_if_present, split_full_name


def map_driving_license_to_deal_create(parsed: dict[str, Any]) -> dict[str, Any]:
    data = parser_data(parsed)
    mapped: dict[str, Any] = {}

    license_no = data.get("license_no")
    set_if_present(
        mapped,
        "license_no",
        license_no,
        aliases=("LicenseNumber", "licence_no", "license_number"),
    )

    issue = parse_date(data.get("issue_date") or data.get("license_from_date"))
    set_if_present(
        mapped,
        "license_from_date",
        issue,
        aliases=("issue_date", "DateOfIssue", "valid_from"),
    )

    expiry = parse_date(data.get("expiry_date") or data.get("license_to_date"))
    set_if_present(
        mapped,
        "license_to_date",
        expiry,
        aliases=("license_expiry_date", "DateOfExpiration", "expiry_date"),
    )

    dob = parse_date(data.get("date_of_birth"))
    set_if_present(mapped, "date_of_birth", dob, aliases=("dob", "birth_date"))

    nationality = data.get("nationality")
    set_if_present(mapped, "nationality", nationality, aliases=("Nationality",))

    name = data.get("name")
    if name:
        first, last = split_full_name(str(name))
        set_if_present(mapped, "first_name", first)
        set_if_present(mapped, "last_name", last)
        set_if_present(mapped, "name", str(name).strip())

    place = data.get("place_of_issue")
    set_if_present(
        mapped,
        "emirate",
        place,
        aliases=("IssuingPlace", "issuing_place", "region"),
    )

    traffic_code = data.get("traffic_code")
    set_if_present(
        mapped,
        "tcf_number",
        traffic_code,
        aliases=("tcf_no", "TCFNumber", "traffic_file_no"),
    )

    return mapped

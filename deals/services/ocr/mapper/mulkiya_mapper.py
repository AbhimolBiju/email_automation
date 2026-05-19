"""Map Mulkiya parser output to deal_create CRM fields."""

from __future__ import annotations

from typing import Any

from apps.ocr.field_transformers import parse_date, parse_plate_source

from .base import parser_data, set_if_present


def map_mulkiya_to_deal_create(parsed: dict[str, Any]) -> dict[str, Any]:
    data = parser_data(parsed)
    mapped: dict[str, Any] = {}

    plate_code = data.get("plate_code")
    set_if_present(
        mapped,
        "plate_code",
        plate_code,
        aliases=("traffic_plate_no", "plate_category"),
    )

    registration_no = data.get("registration_no") or data.get("plate_number")
    set_if_present(
        mapped,
        "registration_no",
        registration_no,
        aliases=("reg_number", "RegistrationNumber", "LicensePlate"),
    )

    reg_date = parse_date(data.get("registration_date"))
    set_if_present(
        mapped,
        "registration_date",
        reg_date,
        aliases=("RegDate", "Reg_Date", "reg_date"),
    )

    plate_source = data.get("plate_source") or data.get("place_of_issue")
    if plate_source:
        normalized = parse_plate_source(plate_source)
        set_if_present(
            mapped,
            "plate_source",
            normalized or plate_source,
            aliases=(
                "place_of_issue",
                "PlaceOfIssue",
                "LicensingAuthority",
                "origin",
            ),
        )

    tcf = data.get("tcf_no") or data.get("tcf_number")
    set_if_present(
        mapped,
        "tcf_number",
        tcf,
        aliases=("tcf_no", "TCFNumber", "TcfNumber", "traffic_file_no"),
    )

    chassis = data.get("chassis_no") or data.get("chassis_number")
    set_if_present(
        mapped,
        "chassis_no",
        chassis,
        aliases=("chassis_number", "vin", "VehicleIdentificationNumber"),
    )

    model_year = data.get("model_year") or data.get("year")
    set_if_present(
        mapped,
        "model_year",
        model_year,
        aliases=("ModelYear", "year"),
    )

    make = data.get("make") or data.get("make_id")
    set_if_present(mapped, "make_id", make, aliases=("manufacturer", "Make"))

    model = data.get("model") or data.get("model_id")
    set_if_present(mapped, "model_id", model, aliases=("Model",))

    body_type = data.get("vehicle_type") or data.get("body_type_id")
    set_if_present(mapped, "body_type_id", body_type, aliases=("body_type",))

    owner = data.get("owner")
    if owner:
        set_if_present(mapped, "name", owner)
        set_if_present(mapped, "customer_name", owner)

    nationality = data.get("nationality")
    set_if_present(mapped, "nationality", nationality, aliases=("Nationality",))

    origin = data.get("origin")
    if origin:
        gcc = "Yes" if str(origin).strip().upper() in {"GCC", "UAE", "UNITED ARAB EMIRATES"} else "No"
        mapped["is_gcc_spec"] = gcc
        mapped["gcc_spec"] = gcc

    return mapped

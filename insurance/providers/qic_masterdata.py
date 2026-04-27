from __future__ import annotations

from pathlib import Path
from typing import Any

from .masterdata_json import ProviderJsonMasterdata, normalize_masterdata_value
from .xlsx_loader import load_workbook_rows


MASTERDATA_ROOT = (
    Path(__file__).resolve().parents[2] / "data" / "providers" / "QIC" / "masterdata"
)
JSON_ROOT = Path(__file__).resolve().parents[2] / "data" / "providers" / "QIC" / "json"

_LOADER = ProviderJsonMasterdata("QIC", JSON_ROOT)


def _load_file(name: str) -> dict[str, list[list[str]]]:
    return load_workbook_rows(MASTERDATA_ROOT / name)


def _excel_body_type_records(_dataset: str) -> list[dict[str, str]]:
    rows = _load_file("Body_type_with_Bayanaty_MasterData.xlsx").get("Sheet1", [])
    return [
        {
            "body_type_code": str(row[0]).strip(),
            "body_type_desc": str(row[1]).strip(),
            "bayanaty_body_type_code": str(row[2]).strip(),
        }
        for row in rows[1:]
        if len(row) >= 3 and any(str(value).strip() for value in row)
    ]


def _excel_make_model_records(_dataset: str) -> list[dict[str, str]]:
    rows = _load_file("Make_Model_list_with_Bayanaty_MasterData.xlsx").get("Sheet1", [])
    records: list[dict[str, str]] = []
    for row in rows[1:]:
        if len(row) < 7 or not any(str(value).strip() for value in row):
            continue
        records.append(
            {
                "make_code": str(row[0]).strip(),
                "make_desc": str(row[1]).strip(),
                "model_code": str(row[2]).strip(),
                "model_desc": str(row[3]).strip(),
                "model_desc_long": str(row[4]).strip(),
                "bayanaty_make_code": str(row[5]).strip(),
                "bayanaty_model_code": str(row[6]).strip(),
            }
        )
    return records


def _excel_nationality_records(_dataset: str) -> list[dict[str, str]]:
    rows = _load_file("Nationality_list_Bayanaty_MasterData.xlsx").get("Sheet1", [])
    return [
        {
            "nationality_code": str(row[0]).strip(),
            "nationality_desc": str(row[1]).strip(),
        }
        for row in rows[1:]
        if len(row) >= 2 and any(str(value).strip() for value in row)
    ]


def _excel_cylinder_records(_dataset: str) -> list[dict[str, str]]:
    rows = _load_file("No_Of_Cylinder_Bayanaty_MasterData.xlsx").get("Sheet1", [])
    return [
        {
            "cylinder_code": str(row[0]).strip(),
            "cylinder_desc": str(row[1]).strip(),
            "cylinder_long_desc": str(row[2]).strip(),
        }
        for row in rows[1:]
        if len(row) >= 3 and any(str(value).strip() for value in row)
    ]


def _excel_regn_location_records(_dataset: str) -> list[dict[str, str]]:
    rows = _load_file("RegnLocation _MasterData.xlsx").get("Sheet1", [])
    records: list[dict[str, str]] = []
    for row in rows:
        if len(row) < 4:
            continue
        if str(row[2]).strip().lower() == "regnlocation":
            continue
        if row[2] in (None, "") and row[3] in (None, ""):
            continue
        records.append(
            {
                "regn_location": str(row[2]).strip(),
                "regn_location_code": str(row[3]).strip(),
            }
        )
    return [record for record in records if record["regn_location"]]


def load_body_type_records() -> list[dict[str, str]]:
    return _LOADER.require_records("body_types", fallback_loader=_excel_body_type_records)


def load_make_model_records() -> list[dict[str, str]]:
    return _LOADER.require_records("make_models", fallback_loader=_excel_make_model_records)


def load_nationality_records() -> list[dict[str, str]]:
    return _LOADER.require_records("nationalities", fallback_loader=_excel_nationality_records)


def load_cylinder_records() -> list[dict[str, str]]:
    return _LOADER.require_records("cylinders", fallback_loader=_excel_cylinder_records)


def load_regn_location_records() -> list[dict[str, str]]:
    return _LOADER.require_records("registration_locations", fallback_loader=_excel_regn_location_records)


def lookup_nationality_code(value: Any) -> str:
    normalized = normalize_masterdata_value(value)
    for record in load_nationality_records():
        if (
            normalize_masterdata_value(record["nationality_code"]) == normalized
            or normalize_masterdata_value(record["nationality_desc"]) == normalized
        ):
            return record["nationality_code"]
    return str(value).strip() if value not in (None, "") else ""


def lookup_make_model_codes(make_value: Any, model_value: Any) -> tuple[str, str]:
    normalized_make = normalize_masterdata_value(make_value)
    normalized_model = normalize_masterdata_value(model_value)
    for record in load_make_model_records():
        make_matches = (
            normalize_masterdata_value(record["make_code"]) == normalized_make
            or normalize_masterdata_value(record["make_desc"]) == normalized_make
        )
        model_matches = (
            normalize_masterdata_value(record["model_code"]) == normalized_model
            or normalize_masterdata_value(record["model_desc"]) == normalized_model
            or normalize_masterdata_value(record["model_desc_long"]) == normalized_model
        )
        if make_matches and model_matches:
            return record["make_code"], record["model_code"]
    return str(make_value).strip(), str(model_value).strip()


def lookup_bayanaty_make_model_ids(make_value: Any, model_value: Any) -> tuple[str, str]:
    normalized_make = normalize_masterdata_value(make_value)
    normalized_model = normalize_masterdata_value(model_value)
    for record in load_make_model_records():
        make_matches = (
            normalize_masterdata_value(record["make_code"]) == normalized_make
            or normalize_masterdata_value(record["make_desc"]) == normalized_make
        )
        model_matches = (
            normalize_masterdata_value(record["model_code"]) == normalized_model
            or normalize_masterdata_value(record["model_desc"]) == normalized_model
            or normalize_masterdata_value(record["model_desc_long"]) == normalized_model
        )
        if make_matches and model_matches:
            return record["bayanaty_make_code"], record["bayanaty_model_code"]
    return str(make_value).strip(), str(model_value).strip()


def lookup_body_type_code(value: Any) -> str:
    normalized = normalize_masterdata_value(value)
    for record in load_body_type_records():
        if (
            normalize_masterdata_value(record["body_type_code"]) == normalized
            or normalize_masterdata_value(record["body_type_desc"]) == normalized
        ):
            return record["body_type_code"]
    return str(value).strip() if value not in (None, "") else ""


def lookup_cylinder_code(value: Any) -> str:
    normalized = normalize_masterdata_value(value)
    for record in load_cylinder_records():
        if (
            normalize_masterdata_value(record["cylinder_code"]) == normalized
            or normalize_masterdata_value(record["cylinder_desc"]) == normalized
            or normalize_masterdata_value(record["cylinder_long_desc"]) == normalized
        ):
            return record["cylinder_code"]
    return str(value).strip() if value not in (None, "") else ""


def lookup_regn_location_code(value: Any) -> str:
    normalized = normalize_masterdata_value(value)
    for record in load_regn_location_records():
        if (
            normalize_masterdata_value(record["regn_location"]) == normalized
            or normalize_masterdata_value(record["regn_location_code"]) == normalized
        ):
            return record["regn_location_code"]
    return str(value).strip() if value not in (None, "") else ""


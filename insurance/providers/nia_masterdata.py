from __future__ import annotations

from pathlib import Path
from typing import Any

from .masterdata_json import ProviderJsonMasterdata, normalize_masterdata_value

# normalize_masterdata_value strips, uppercases, and compares alphanumerics only — case-insensitive
# for Latin text. It does not equate different words (e.g. "Yemen" vs sheet "YEMENI"); nationality
# uses extra fuzzy matching in NIAProvider._resolve_nationality_code.
from .xlsx_loader import load_workbook_rows


MASTERDATA_ROOT = (
    Path(__file__).resolve().parents[2] / "data" / "providers" / "NIA" / "masterdata"
)
JSON_ROOT = Path(__file__).resolve().parents[2] / "data" / "providers" / "NIA" / "json"

_LOADER = ProviderJsonMasterdata("NIA", JSON_ROOT)


def _mapping_workbook() -> dict[str, list[list[str]]]:
    return load_workbook_rows(MASTERDATA_ROOT / "Mapping data.xlsx")


def _plate_mapping_workbook() -> dict[str, list[list[str]]]:
    return load_workbook_rows(MASTERDATA_ROOT / "Plate Code Mapping.xlsx")


def _excel_sheet_records(sheet_name: str) -> list[dict[str, str]]:
    rows = _mapping_workbook().get(sheet_name, [])
    if not rows:
        return []
    headers = [str(cell).strip() for cell in rows[0]]
    records: list[dict[str, str]] = []
    for row in rows[1:]:
        if not any(str(value).strip() for value in row):
            continue
        record: dict[str, str] = {}
        for idx, header in enumerate(headers):
            if not header:
                continue
            record[header] = str(row[idx]).strip() if idx < len(row) and row[idx] is not None else ""
        records.append(record)
    return records


def _excel_plate_code_records(_dataset: str) -> list[dict[str, str]]:
    rows = _plate_mapping_workbook().get("Sheet1", [])
    if not rows:
        return []
    headers = [str(cell).strip() if cell is not None else "" for cell in rows[0]]
    records: list[dict[str, str]] = []
    for row in rows[1:]:
        if len(row) < 6 or not any(str(value).strip() for value in row):
            continue
        record: dict[str, str] = {}
        for idx, header in enumerate(headers):
            if not header:
                continue
            record[header] = str(row[idx]).strip() if idx < len(row) and row[idx] is not None else ""
        records.append(record)
    return records


def load_sheet_records(sheet_name: str) -> list[dict[str, str]]:
    return _LOADER.require_records(sheet_name, fallback_loader=_excel_sheet_records)


def load_plate_code_records() -> list[dict[str, str]]:
    return _LOADER.require_records("PlateCodeMapping", fallback_loader=_excel_plate_code_records)


def lookup_code(
    sheet_name: str,
    value: Any,
    *,
    code_key: str = "Code",
    description_key: str = "Description",
    default: str = "",
) -> str:
    text = str(value).strip() if value not in (None, "") else ""
    if not text:
        return default
    normalized = normalize_masterdata_value(text)
    for record in load_sheet_records(sheet_name):
        if normalize_masterdata_value(record.get(code_key, "")) == normalized:
            return record.get(code_key, "")
        if normalize_masterdata_value(record.get(description_key, "")) == normalized:
            return record.get(code_key, "")
    return default or text


def lookup_description(
    sheet_name: str,
    value: Any,
    *,
    code_key: str = "Code",
    description_key: str = "Description",
    default: str = "",
) -> str:
    text = str(value).strip() if value not in (None, "") else ""
    if not text:
        return default
    normalized = normalize_masterdata_value(text)
    for record in load_sheet_records(sheet_name):
        if normalize_masterdata_value(record.get(code_key, "")) == normalized:
            return record.get(description_key, "")
        if normalize_masterdata_value(record.get(description_key, "")) == normalized:
            return record.get(description_key, "")
    return default or text


def lookup_plate_color_code(value: Any, reg_city: Any) -> str:
    normalized_value = normalize_masterdata_value(value)
    normalized_city = normalize_masterdata_value(reg_city)
    for record in load_plate_code_records():
        if (
            normalize_masterdata_value(record.get("Description", "")) == normalized_value
            and normalize_masterdata_value(record.get("Reg. City", "")) == normalized_city
        ):
            return record.get("Code", "")
    return str(value).strip() if value not in (None, "") else ""


def lookup_body_code_from_model(model_code: Any) -> tuple[str, str]:
    text = str(model_code).strip() if model_code not in (None, "") else ""
    if not text:
        return "", ""
    normalized = normalize_masterdata_value(text)
    for record in load_sheet_records("VehModel"):
        if record.get("MODEL CODE", "").strip() == text:
            return record.get("BODY CODE", "").strip(), record.get("BODY DESC", "").strip()
        if normalize_masterdata_value(record.get("MODE DESCRIPTION", "")) == normalized:
            return record.get("BODY CODE", "").strip(), record.get("BODY DESC", "").strip()
    return "", ""


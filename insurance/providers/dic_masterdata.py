from __future__ import annotations

from pathlib import Path
from typing import Any

from .masterdata_json import ProviderJsonMasterdata, normalize_masterdata_value
from .xlsx_loader import load_workbook_rows


MASTERDATA_ROOT = (
    Path(__file__).resolve().parents[2] / "data" / "providers" / "DIC" / "masterdata"
)
JSON_ROOT = Path(__file__).resolve().parents[2] / "data" / "providers" / "DIC" / "json"

MASTERDATA_FILE_MAP = {
    "bank_name": "Bank Name.xlsx",
    "emirate": "Emirites.xlsx",
    "gender": "Gender.xlsx",
    "nationality": "Nationality.xlsx",
    "ncd_years": "NcdYears.xlsx",
    "plate_code": "PlateCode.xlsx",
    "plate_source": "PlateSource.xlsx",
    "traffic_transaction_type": "TrafficTransType.xlsx",
}

_LOADER = ProviderJsonMasterdata("DIC", JSON_ROOT)


def _excel_records(dataset: str) -> list[dict[str, str]]:
    workbook = load_workbook_rows(MASTERDATA_ROOT / MASTERDATA_FILE_MAP[dataset])
    rows = next(iter(workbook.values()), [])
    if not rows:
        return []
    headers = [str(cell).strip().lower() for cell in rows[0]]
    code_idx = headers.index("code")
    description_idx = headers.index("description")
    records: list[dict[str, str]] = []
    for row in rows[1:]:
        if len(row) <= code_idx:
            continue
        code = str(row[code_idx]).strip()
        if not code:
            continue
        description = str(row[description_idx]).strip() if len(row) > description_idx else ""
        records.append({"code": code, "description": description})
    return records


def load_masterdata(dataset: str) -> list[dict[str, str]]:
    return _LOADER.require_records(dataset, fallback_loader=_excel_records)


def list_masterdata(dataset: str) -> list[dict[str, str]]:
    return list(load_masterdata(dataset))


def lookup_code(dataset: str, value: Any, *, default: str = "") -> str:
    text = str(value).strip() if value not in (None, "") else ""
    if not text:
        return default
    normalized_value = normalize_masterdata_value(text)
    for record in load_masterdata(dataset):
        if normalize_masterdata_value(record["code"]) == normalized_value:
            return record["code"]
        if normalize_masterdata_value(record["description"]) == normalized_value:
            return record["code"]
    return default or text


def lookup_description(dataset: str, value: Any, *, default: str = "") -> str:
    text = str(value).strip() if value not in (None, "") else ""
    if not text:
        return default
    normalized_value = normalize_masterdata_value(text)
    for record in load_masterdata(dataset):
        if normalize_masterdata_value(record["code"]) == normalized_value:
            return record["description"]
        if normalize_masterdata_value(record["description"]) == normalized_value:
            return record["description"]
    return default or text

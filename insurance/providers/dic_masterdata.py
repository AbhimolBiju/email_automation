from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any
from xml.etree import ElementTree
from zipfile import ZipFile


MASTERDATA_ROOT = (
    Path(__file__).resolve().parents[2] / "data" / "providers" / "DIC" / "masterdata"
)

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


def _normalize(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().upper()
    text = text.replace("&", "AND")
    text = re.sub(r"[^A-Z0-9]+", "", text)
    return text


@lru_cache(maxsize=None)
def load_masterdata(dataset: str) -> list[dict[str, str]]:
    filename = MASTERDATA_FILE_MAP[dataset]
    workbook_path = MASTERDATA_ROOT / filename
    with ZipFile(workbook_path) as archive:
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared_tree = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            for item in shared_tree.findall("x:si", namespace):
                text = "".join(node.text or "" for node in item.findall(".//x:t", namespace))
                shared_strings.append(text)

        sheet_tree = ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

        rows: list[list[str]] = []
        for row in sheet_tree.findall(".//x:sheetData/x:row", namespace):
            values: list[str] = []
            for cell in row.findall("x:c", namespace):
                cell_type = cell.attrib.get("t")
                value_node = cell.find("x:v", namespace)
                value = value_node.text if value_node is not None else ""
                if cell_type == "s" and value:
                    value = shared_strings[int(value)]
                values.append(value or "")
            rows.append(values)

    records: list[dict[str, str]] = []
    for row in rows[1:]:
        if not row or row[0] in (None, ""):
            continue
        code = str(row[0]).strip()
        description = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""
        records.append({"code": code, "description": description})
    return records


def list_masterdata(dataset: str) -> list[dict[str, str]]:
    return list(load_masterdata(dataset))


def lookup_code(dataset: str, value: Any, *, default: str = "") -> str:
    text = str(value).strip() if value not in (None, "") else ""
    if not text:
        return default
    normalized_value = _normalize(text)
    for record in load_masterdata(dataset):
        if _normalize(record["code"]) == normalized_value:
            return record["code"]
        if _normalize(record["description"]) == normalized_value:
            return record["code"]
    return default or text


def lookup_description(dataset: str, value: Any, *, default: str = "") -> str:
    text = str(value).strip() if value not in (None, "") else ""
    if not text:
        return default
    normalized_value = _normalize(text)
    for record in load_masterdata(dataset):
        if _normalize(record["code"]) == normalized_value:
            return record["description"]
        if _normalize(record["description"]) == normalized_value:
            return record["description"]
    return default or text

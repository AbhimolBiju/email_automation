from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile


MAIN_NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_NS = {"r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
PKG_REL_NS = {"pr": "http://schemas.openxmlformats.org/package/2006/relationships"}


def _column_index(cell_ref: str) -> int:
    letters = "".join(ch for ch in cell_ref if ch.isalpha())
    index = 0
    for char in letters:
        index = (index * 26) + (ord(char.upper()) - 64)
    return max(index - 1, 0)


def _shared_strings(archive: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    shared_tree = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    values: list[str] = []
    for item in shared_tree.findall("x:si", MAIN_NS):
        text = "".join(node.text or "" for node in item.findall(".//x:t", MAIN_NS))
        values.append(text)
    return values


def _sheet_targets(archive: ZipFile) -> dict[str, str]:
    workbook_tree = ElementTree.fromstring(archive.read("xl/workbook.xml"))
    rel_tree = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    rel_map = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rel_tree.findall("pr:Relationship", PKG_REL_NS)
    }
    targets: dict[str, str] = {}
    for sheet in workbook_tree.findall("x:sheets/x:sheet", MAIN_NS):
        name = sheet.attrib["name"]
        rel_id = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        if rel_id and rel_id in rel_map:
            targets[name] = f"xl/{rel_map[rel_id]}"
    return targets


def load_workbook_rows(path: str | Path) -> dict[str, list[list[str]]]:
    workbook_path = Path(path)
    with ZipFile(workbook_path) as archive:
        shared_strings = _shared_strings(archive)
        sheet_paths = _sheet_targets(archive)
        workbook: dict[str, list[list[str]]] = {}
        for sheet_name, internal_path in sheet_paths.items():
            sheet_tree = ElementTree.fromstring(archive.read(internal_path))
            rows: list[list[str]] = []
            for row in sheet_tree.findall(".//x:sheetData/x:row", MAIN_NS):
                values: list[str] = []
                current_index = 0
                for cell in row.findall("x:c", MAIN_NS):
                    cell_ref = cell.attrib.get("r", "")
                    target_index = _column_index(cell_ref) if cell_ref else current_index
                    while len(values) < target_index:
                        values.append("")
                    cell_type = cell.attrib.get("t")
                    value_node = cell.find("x:v", MAIN_NS)
                    inline_node = cell.find("x:is/x:t", MAIN_NS)
                    value = ""
                    if inline_node is not None and inline_node.text is not None:
                        value = inline_node.text
                    elif value_node is not None and value_node.text is not None:
                        value = value_node.text
                    if cell_type == "s" and value:
                        value = shared_strings[int(value)]
                    values.append(value)
                    current_index = len(values)
                rows.append(values)
            workbook[sheet_name] = rows
        return workbook

from __future__ import annotations

import logging
from pathlib import Path
import re
from typing import Any

from .masterdata_json import ProviderJsonMasterdata, normalize_masterdata_value
from .xlsx_loader import load_workbook_rows

logger = logging.getLogger(__name__)

MASTERDATA_ROOT = (
    Path(__file__).resolve().parents[2] / "data" / "providers" / "QIC" / "masterdata"
)
JSON_ROOT = Path(__file__).resolve().parents[2] / "data" / "providers" / "QIC" / "json"

_LOADER = ProviderJsonMasterdata("QIC", JSON_ROOT)


# ---------------------------------------------------------------------------
# Excel loaders
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Public loaders
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Private shared helper: fuzzy make+model matching
# ---------------------------------------------------------------------------

def _match_make_model_record(
    records: list[dict[str, str]],
    make_value: Any,
    model_value: Any,
) -> dict[str, str] | None:
    """
    Try to find a matching make/model record using 3 progressive passes:

    Pass 1 — Exact match on both make and model fields.
              e.g. input "Outlander" == masterdata model_desc "Outlander"

    Pass 2 — Exact make + input STARTS WITH masterdata model description.
              e.g. input "OUTLANDER GLS BASE" starts with masterdata "OUTLANDER"

    Pass 3 — Exact make + masterdata model description IS CONTAINED IN input.
              e.g. masterdata "OUTLANDER" is a substring of "OUTLANDER GLS BASE"

    Returns the first matched record dict, or None if no match found.
    """
    normalized_make = normalize_masterdata_value(make_value)
    normalized_model = normalize_masterdata_value(model_value)

    # ── Pass 1: exact match on both make and model ───────────────────────────
    for record in records:
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
            return record

    # Filter to records where make already matches — used in passes 2 & 3
    make_filtered = [
        r for r in records
        if normalize_masterdata_value(r["make_code"]) == normalized_make
        or normalize_masterdata_value(r["make_desc"]) == normalized_make
    ]

    if not make_filtered:
        return None

    # ── Pass 2: input starts with masterdata model description ───────────────
    for record in make_filtered:
        norm_desc = normalize_masterdata_value(record["model_desc"])
        norm_long = normalize_masterdata_value(record["model_desc_long"])
        if norm_desc and normalized_model.startswith(norm_desc):
            logger.info(
                "QIC make/model partial match (startswith): input=%r -> "
                "make_desc=%r model_desc=%r (make_code=%s model_code=%s)",
                model_value,
                record["make_desc"],
                record["model_desc"],
                record["make_code"],
                record["model_code"],
            )
            return record
        if norm_long and normalized_model.startswith(norm_long):
            logger.info(
                "QIC make/model partial match (startswith long): input=%r -> "
                "make_desc=%r model_desc_long=%r (make_code=%s model_code=%s)",
                model_value,
                record["make_desc"],
                record["model_desc_long"],
                record["make_code"],
                record["model_code"],
            )
            return record

    # ── Pass 3: masterdata model description is contained in input ───────────
    for record in make_filtered:
        norm_desc = normalize_masterdata_value(record["model_desc"])
        norm_long = normalize_masterdata_value(record["model_desc_long"])
        if norm_desc and norm_desc in normalized_model:
            logger.info(
                "QIC make/model partial match (substring): input=%r -> "
                "make_desc=%r model_desc=%r (make_code=%s model_code=%s)",
                model_value,
                record["make_desc"],
                record["model_desc"],
                record["make_code"],
                record["model_code"],
            )
            return record
        if norm_long and norm_long in normalized_model:
            logger.info(
                "QIC make/model partial match (substring long): input=%r -> "
                "make_desc=%r model_desc_long=%r (make_code=%s model_code=%s)",
                model_value,
                record["make_desc"],
                record["model_desc_long"],
                record["make_code"],
                record["model_code"],
            )
            return record

    return None


# ---------------------------------------------------------------------------
# Public lookup functions
# ---------------------------------------------------------------------------

def lookup_nationality_code(value: Any) -> str:
    """
    Map nationality input (QIC code or description) to QIC nationality_code.
    Returns the code if found, otherwise returns empty string (for validation to catch).
    """
    normalized = normalize_masterdata_value(value)
    for record in load_nationality_records():
        if (
            normalize_masterdata_value(record["nationality_code"]) == normalized
            or normalize_masterdata_value(record["nationality_desc"]) == normalized
        ):
            return record["nationality_code"]
    if value not in (None, ""):
        logger.warning("QIC lookup_nationality_code: unable to map value=%r", value)
    return ""


def lookup_make_model_codes(make_value: Any, model_value: Any) -> tuple[str, str]:
    """
    Map make/model input to QIC make_code and model_code.
    Uses 3-pass fuzzy matching: exact → startswith → substring.
    Falls back to raw input strings if no match found (guard in qic_provider.py catches this).
    """
    record = _match_make_model_record(load_make_model_records(), make_value, model_value)
    if record:
        return record["make_code"], record["model_code"]

    logger.warning(
        "QIC lookup_make_model_codes: unable to map make=%r model=%r",
        make_value,
        model_value,
    )
    return str(make_value).strip(), str(model_value).strip()


def lookup_bayanaty_make_model_ids(make_value: Any, model_value: Any) -> tuple[str, str]:
    """
    Map make/model input to Bayanaty make/model codes.
    Uses the same 3-pass fuzzy matching as lookup_make_model_codes.
    Falls back to raw input strings if no match found.
    """
    record = _match_make_model_record(load_make_model_records(), make_value, model_value)
    if record:
        return record["bayanaty_make_code"], record["bayanaty_model_code"]

    logger.warning(
        "QIC lookup_bayanaty_make_model_ids: unable to map make=%r model=%r",
        make_value,
        model_value,
    )
    return str(make_value).strip(), str(model_value).strip()


def lookup_body_type_code(value: Any) -> str:
    """
    Map body type input (QIC code or description) to QIC body_type_code.
    Returns the code if found, otherwise returns empty string (for validation to catch).
    """
    normalized = normalize_masterdata_value(value)
    for record in load_body_type_records():
        if (
            normalize_masterdata_value(record["body_type_code"]) == normalized
            or normalize_masterdata_value(record["body_type_desc"]) == normalized
        ):
            return record["body_type_code"]
    logger.warning("QIC lookup_body_type_code: unable to map value=%r", value)
    return ""


def lookup_body_type_code_from_desc(body_desc: str) -> str:
    _ALIASES = {
        "4X4": "4 X 4",
        "SUV": "4 X 4",
        "HATCH BACK": "HATCHBACK",
        "PICK UP": "PICKUP UPTO 2.5 TON",
        "PICKUP": "PICKUP UPTO 2.5 TON",
        "VAN": "VAN UPTO 3 TON",
        "EQUIPMENTS": "EQUIPMENT > 3 TON",
    }
    normalized = body_desc.strip().upper()
    normalized = _ALIASES.get(normalized, normalized)
    for record in load_body_type_records():
        if record.get("body_type_desc", "").strip().upper() == normalized:
            return record.get("body_type_code", "")
    return ""


def lookup_body_type_code_from_bayanaty(value: Any) -> str:
    """Map a Bayanaty body type code (e.g. '500116') to a QIC body_type_code (e.g. '1001').
    The bayanaty_body_type_code column stores comma-delimited values like ',500116,500134,'
    so we check for substring containment."""
    if value in (None, ""):
        return ""
    search = f",{str(value).strip()},"
    for record in load_body_type_records():
        bayanaty_field = record.get("bayanaty_body_type_code", "")
        if search in bayanaty_field:
            return record["body_type_code"]
    logger.warning("QIC lookup_body_type_code_from_bayanaty: unable to map value=%r", value)
    return ""



def lookup_cylinder_code(value: Any) -> str:
    """
    Map cylinder input (QIC code, internal ID, or displacement) to QIC cylinder_code.

    Strategy:
    1. If input matches a QIC cylinder_code directly, return it (e.g., '1004' -> '1004')
    2. If input matches cylinder_desc or cylinder_long_desc, return the code
    3. If input is a displacement string (e.g., '2.0 L', '2000 CC'), extract number and match
    4. If input is a numeric string or number, match as cylinder count (e.g., '4' -> '1004')
    5. Otherwise return empty string (invalid) for validation to catch
    """
    normalized = normalize_masterdata_value(value)
    records = load_cylinder_records()

    # Exact code/description match
    for record in records:
        if (
            normalize_masterdata_value(record["cylinder_code"]) == normalized
            or normalize_masterdata_value(record["cylinder_desc"]) == normalized
            or normalize_masterdata_value(record["cylinder_long_desc"]) == normalized
        ):
            return record["cylinder_code"]

    # Try to parse as displacement string (e.g., "2.0 L", "1600cc", "4.0L")
    if isinstance(value, str):
        raw = value.strip()
        if raw:
            match = re.search(r"(\d+(?:\.\d+)?)\s*(L|LTR|LITRE|LITER|CC|CM3)?", raw, flags=re.IGNORECASE)
            if match:
                number_str = match.group(1)
                unit = (match.group(2) or "").upper()
                candidates: list[str] = []

                if unit in ("L", "LTR", "LITRE", "LITER", ""):
                    try:
                        candidates.append(str(int(float(number_str))))
                    except Exception:
                        pass

                if unit in ("CC", "CM3"):
                    candidates.append(number_str)
                    try:
                        liters = float(number_str) / 1000.0
                        candidates.append(f"{liters:.1f}")
                    except Exception:
                        pass

                for candidate in candidates:
                    candidate_norm = normalize_masterdata_value(candidate)
                    for record in records:
                        desc_norm = normalize_masterdata_value(record["cylinder_desc"])
                        long_norm = normalize_masterdata_value(record["cylinder_long_desc"])
                        if candidate_norm and (candidate_norm in desc_norm or candidate_norm in long_norm):
                            return record["cylinder_code"]

    # Try to match as bare number (e.g., '4' -> look for '4 cylinders')
    if isinstance(value, (int, str)):
        try:
            num = int(str(value).strip())
            num_norm = normalize_masterdata_value(str(num))
            for record in records:
                desc_norm = normalize_masterdata_value(record["cylinder_desc"])
                long_norm = normalize_masterdata_value(record["cylinder_long_desc"])
                if num_norm == desc_norm or num_norm in long_norm:
                    return record["cylinder_code"]
        except Exception:
            pass

    logger.warning("QIC lookup_cylinder_code: unable to map value=%r", value)
    return ""


def lookup_regn_location_code(value: Any) -> str:
    """
    Map registration location input (place name or QIC code) to QIC regn_location_code.
    Valid codes: 1 (Dubai), 2 (Sharjah), 3 (Ajman), 4 (Abu Dhabi), 5 (RAK), 6 (UAQ), 7 (Fujairah).
    Returns zero-padded 3-digit code (e.g. '001') or empty string if not found.
    """
    normalized = normalize_masterdata_value(value)
    for record in load_regn_location_records():
        if (
            normalize_masterdata_value(record["regn_location"]) == normalized
            or normalize_masterdata_value(record["regn_location_code"]) == normalized
        ):
            return str(record["regn_location_code"]).zfill(3)  # '1' → '001'
    if value not in (None, ""):
        logger.warning(
            "QIC lookup_regn_location_code: unable to map value=%r "
            "(valid: Dubai, Sharjah, Ajman, Abu Dhabi, RAK, UAQ, Fujairah)",
            value,
        )
    return ""
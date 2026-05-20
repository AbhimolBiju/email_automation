from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from insurance.providers.xlsx_loader import load_workbook_rows


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PROVIDERS_ROOT = PROJECT_ROOT / "data" / "providers"


class Command(BaseCommand):
    help = "Build precompiled JSON masterdata for DIC, NIA, and QIC from source Excel files."

    def add_arguments(self, parser):
        parser.add_argument(
            "--provider",
            action="append",
            choices=["dic", "nia", "qic"],
            help="Only build masterdata for the selected provider. Can be passed multiple times.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing generated JSON files.",
        )

    def handle(self, *args, **options):
        providers = options["provider"] or ["dic", "nia", "qic"]
        for provider in providers:
            builder = getattr(self, f"_build_{provider}")
            summary = builder(force=options["force"])
            self.stdout.write(
                self.style.SUCCESS(
                    f"{provider.upper()}: wrote {summary['datasets']} datasets, {summary['records']} records to {summary['json_dir']}"
                )
            )

    def _write_dataset(
        self,
        provider_code: str,
        dataset: str,
        records: list[dict[str, str]],
        *,
        force: bool,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[Path, int]:
        json_dir = PROVIDERS_ROOT / provider_code / "json"
        json_dir.mkdir(parents=True, exist_ok=True)
        path = json_dir / f"{dataset}.json"
        if path.exists() and not force:
            raise CommandError(f"{path} already exists. Use --force to overwrite generated JSON.")

        if records and all("code" in record for record in records):
            codes = [str(record.get("code", "")).strip() for record in records if str(record.get("code", "")).strip()]
            duplicates = [code for code, count in Counter(codes).items() if count > 1]
            if duplicates:
                raise CommandError(
                    f"Duplicate codes found in {provider_code.upper()} dataset '{dataset}': {', '.join(duplicates[:10])}"
                )

        payload = {
            "metadata": metadata or {},
            "records": records,
        }
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        return path, len(records)

    def _build_dic(self, *, force: bool) -> dict[str, Any]:
        file_map = {
            "bank_name": "Bank Name.xlsx",
            "emirate": "Emirites.xlsx",
            "gender": "Gender.xlsx",
            "nationality": "Nationality.xlsx",
            "ncd_years": "NcdYears.xlsx",
            "plate_code": "PlateCode.xlsx",
            "plate_source": "PlateSource.xlsx",
            "traffic_transaction_type": "TrafficTransType.xlsx",
        }
        record_count = 0
        for dataset, filename in file_map.items():
            workbook = load_workbook_rows(PROVIDERS_ROOT / "DIC" / "masterdata" / filename)
            rows = next(iter(workbook.values()), [])
            if not rows:
                raise CommandError(f"DIC workbook '{filename}' is empty.")
            headers = [str(cell).strip().lower() for cell in rows[0]]
            if "code" not in headers or "description" not in headers:
                raise CommandError(f"DIC workbook '{filename}' must contain Code and Description headers.")
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
            _, written = self._write_dataset("DIC", dataset, records, force=force, metadata={"source_file": filename})
            record_count += written
        return {"datasets": len(file_map), "records": record_count, "json_dir": PROVIDERS_ROOT / "DIC" / "json"}

    def _build_nia(self, *, force: bool) -> dict[str, Any]:
        mapping_rows = load_workbook_rows(PROVIDERS_ROOT / "NIA" / "masterdata" / "Mapping data.xlsx")
        plate_rows = load_workbook_rows(PROVIDERS_ROOT / "NIA" / "masterdata" / "Plate Code Mapping.xlsx")
        record_count = 0

        for sheet_name, rows in mapping_rows.items():
            if not rows:
                continue
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
                if record:
                    records.append(record)
            _, written = self._write_dataset(
                "NIA",
                sheet_name,
                records,
                force=force,
                metadata={"source_file": "Mapping data.xlsx", "sheet_name": sheet_name},
            )
            record_count += written

        plate_sheet = plate_rows.get("Sheet1", [])
        if not plate_sheet:
            raise CommandError("NIA workbook 'Plate Code Mapping.xlsx' is empty.")
        headers = [str(cell).strip() if cell is not None else "" for cell in plate_sheet[0]]
        plate_records: list[dict[str, str]] = []
        for row in plate_sheet[1:]:
            if len(row) < 6 or not any(str(value).strip() for value in row):
                continue
            record: dict[str, str] = {}
            for idx, header in enumerate(headers):
                if not header:
                    continue
                record[header] = str(row[idx]).strip() if idx < len(row) and row[idx] is not None else ""
            if record:
                plate_records.append(record)
        _, written = self._write_dataset(
            "NIA",
            "PlateCodeMapping",
            plate_records,
            force=force,
            metadata={"source_file": "Plate Code Mapping.xlsx", "sheet_name": "Sheet1"},
        )
        record_count += written
        return {"datasets": len(mapping_rows) + 1, "records": record_count, "json_dir": PROVIDERS_ROOT / "NIA" / "json"}

    def _build_qic(self, *, force: bool) -> dict[str, Any]:
        builders = {
            "body_types": (
                "Body_type_with_Bayanaty_MasterData.xlsx",
                lambda rows: [
                    {
                        "body_type_code": str(row[0]).strip(),
                        "body_type_desc": str(row[1]).strip(),
                        "bayanaty_body_type_code": str(row[2]).strip(),
                    }
                    for row in rows[1:]
                    if len(row) >= 3 and any(str(value).strip() for value in row)
                ],
            ),
            "make_models": (
                "Make_Model_list_with_Bayanaty_MasterData.xlsx",
                lambda rows: [
                    {
                        "make_code": str(row[0]).strip(),
                        "make_desc": str(row[1]).strip(),
                        "model_code": str(row[2]).strip(),
                        "model_desc": str(row[3]).strip(),
                        "model_desc_long": str(row[4]).strip(),
                        "bayanaty_make_code": str(row[5]).strip(),
                        "bayanaty_model_code": str(row[6]).strip(),
                    }
                    for row in rows[1:]
                    if len(row) >= 7 and any(str(value).strip() for value in row)
                ],
            ),
            "nationalities": (
                "Nationality_list_Bayanaty_MasterData.xlsx",
                lambda rows: [
                    {
                        "nationality_code": str(row[0]).strip(),
                        "nationality_desc": str(row[1]).strip(),
                    }
                    for row in rows[1:]
                    if len(row) >= 2 and any(str(value).strip() for value in row)
                ],
            ),
            "cylinders": (
                "No_Of_Cylinder_Bayanaty_MasterData.xlsx",
                lambda rows: [
                    {
                        "cylinder_code": str(row[0]).strip(),
                        "cylinder_desc": str(row[1]).strip(),
                        "cylinder_long_desc": str(row[2]).strip(),
                    }
                    for row in rows[1:]
                    if len(row) >= 3 and any(str(value).strip() for value in row)
                ],
            ),
            "registration_locations": (
                "RegnLocation _MasterData.xlsx",
                lambda rows: [
                    {
                        "regn_location": str(row[2]).strip(),
                        "regn_location_code": str(row[3]).strip(),
                    }
                    for row in rows
                    if len(row) >= 4
                    and str(row[2]).strip().lower() != "regnlocation"
                    and (row[2] not in (None, "") or row[3] not in (None, ""))
                    and str(row[2]).strip()
                ],
            ),
        }
        record_count = 0
        for dataset, (filename, serializer) in builders.items():
            rows = load_workbook_rows(PROVIDERS_ROOT / "QIC" / "masterdata" / filename).get("Sheet1", [])
            if not rows:
                raise CommandError(f"QIC workbook '{filename}' is empty.")
            records = serializer(rows)
            _, written = self._write_dataset("QIC", dataset, records, force=force, metadata={"source_file": filename})
            record_count += written
        return {"datasets": len(builders), "records": record_count, "json_dir": PROVIDERS_ROOT / "QIC" / "json"}

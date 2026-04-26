from typing import Any

from django.core.management.base import BaseCommand

from documents.models import Document
from documents.ocr_parser import extract_structured_fields


RAW_RESPONSE_KEYS = {
    "engine",
    "model_id",
    "confidence",
    "raw_text",
    "pages",
    "source_file",
    "error",
}


def normalized_from_existing_response(document: Document) -> dict[str, Any] | None:
    response = document.ocr_response or {}
    if not isinstance(response, dict):
        return None

    raw_text = response.get("raw_text") or response.get("extracted_text") or ""
    confidence = response.get("confidence")
    if raw_text:
        return extract_structured_fields(
            raw_text,
            confidence=confidence if isinstance(confidence, (int, float)) else None,
            document_type_hint=response.get("document_type") or document.document_type or "other",
        )

    mixed_fields = {
        key: value
        for key, value in response.items()
        if key not in RAW_RESPONSE_KEYS and value not in (None, "")
    }
    if not mixed_fields:
        return None

    mixed_fields.setdefault("document_type", document.document_type or "other")
    return mixed_fields


class Command(BaseCommand):
    help = "Backfill Document.ocr_data from existing Document.ocr_response payloads."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Rebuild ocr_data even when it is already populated.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be updated without saving changes.",
        )

    def handle(self, *args, **options):
        force = options["force"]
        dry_run = options["dry_run"]
        queryset = Document.objects.exclude(ocr_response__isnull=True).order_by("id")

        scanned = 0
        updated = 0
        skipped = 0

        for document in queryset.iterator():
            scanned += 1
            if document.ocr_data and not force:
                skipped += 1
                continue

            ocr_data = normalized_from_existing_response(document)
            if not ocr_data:
                skipped += 1
                continue

            updated += 1
            if dry_run:
                self.stdout.write(
                    f"Would update document {document.id}: {sorted(ocr_data.keys())}"
                )
                continue

            document.ocr_data = ocr_data
            document.save(update_fields=["ocr_data"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Scanned {scanned}, updated {updated}, skipped {skipped}."
            )
        )

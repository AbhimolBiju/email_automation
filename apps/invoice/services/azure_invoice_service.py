"""Azure Document Intelligence client wrapper for prebuilt-invoice analysis."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, BinaryIO

from django.conf import settings

from apps.invoice.exceptions import AzureInvoiceError, InvoiceConfigurationError
from apps.invoice.field_mappings import resolve_model_id
from apps.invoice.serialization import to_json_safe
from apps.invoice.services.invoice_parser import parse_invoice_document
from apps.invoice.services.parser.router import parse_insurance_document

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InvoiceResult:
    """Normalized invoice extraction output from Azure Document Intelligence."""

    raw_fields: dict[str, Any]
    confidence_scores: dict[str, float]
    model_used: str
    page_count: int
    provider_payload: dict[str, Any] = field(default_factory=dict)


class AzureInvoiceService:
    """Thin wrapper around ``DocumentAnalysisClient`` for invoice analysis."""

    def __init__(self) -> None:
        """Load endpoint and key from Django settings."""
        self._endpoint = getattr(settings, "AZURE_FORM_RECOGNIZER_ENDPOINT", "") or ""
        self._key = getattr(settings, "AZURE_FORM_RECOGNIZER_KEY", "") or ""
        self._polling_timeout = int(
            getattr(settings, "INVOICE_POLLING_TIMEOUT_SECONDS", 120)
        )

    def _get_client(self):
        """Build and return an authenticated Document Analysis client."""
        if not self._endpoint or not self._key:
            raise InvoiceConfigurationError(
                "Azure Form Recognizer is not configured. Set "
                "AZURE_FORM_RECOGNIZER_ENDPOINT and AZURE_FORM_RECOGNIZER_KEY."
            )

        try:
            from azure.ai.formrecognizer import DocumentAnalysisClient
            from azure.core.credentials import AzureKeyCredential
        except ModuleNotFoundError as exc:
            raise InvoiceConfigurationError(
                "azure-ai-formrecognizer is not installed."
            ) from exc

        return DocumentAnalysisClient(
            endpoint=self._endpoint.rstrip("/"),
            credential=AzureKeyCredential(self._key),
        )

    def analyze_document(
        self,
        file_obj: BinaryIO,
        *,
        document_type: str,
    ) -> InvoiceResult:
        """Run Azure analysis and return normalized invoice field output."""
        model_id = resolve_model_id(document_type)
        client = self._get_client()

        try:
            poller = client.begin_analyze_document(model_id, file_obj)
            result = poller.result(timeout=self._polling_timeout)
        except InvoiceConfigurationError:
            raise
        except Exception as exc:
            logger.exception(
                "Azure invoice analysis failed for document_type=%s",
                document_type,
            )
            raise AzureInvoiceError(str(exc)) from exc

        raw_fields, confidence_scores = self._extract_fields(result)
        raw_fields = self._enrich_parsed_fields(
            raw_fields,
            confidence_scores,
            result=result,
            document_type=document_type,
        )
        page_count = len(getattr(result, "pages", []) or [])

        return InvoiceResult(
            raw_fields=raw_fields,
            confidence_scores=confidence_scores,
            model_used=model_id,
            page_count=page_count,
            provider_payload={
                "model_id": model_id,
                "document_type": document_type,
                "pages": page_count,
            },
        )

    def _extract_fields(self, result: Any) -> tuple[dict[str, Any], dict[str, float]]:
        """Pull structured key/value pairs and confidences from the analyze result."""
        raw_fields: dict[str, Any] = {}
        confidence_scores: dict[str, float] = {}

        documents = getattr(result, "documents", None) or []
        for document in documents:
            doc_fields = getattr(document, "fields", None) or {}
            for name, azure_field in doc_fields.items():
                value = self._field_value(azure_field)
                if value is not None:
                    raw_fields[name] = to_json_safe(value)
                confidence = getattr(azure_field, "confidence", None)
                if isinstance(confidence, (int, float)):
                    confidence_scores[name] = float(confidence)

        content = getattr(result, "content", None)
        if content:
            raw_fields.setdefault("content", content)
            confidence_scores.setdefault(
                "content",
                self._average_word_confidence(result),
            )

        return raw_fields, confidence_scores

    @staticmethod
    def _polygon_box(polygon: Any) -> dict[str, float] | None:
        """Convert an Azure polygon into a simple axis-aligned bounding box."""
        if polygon is None:
            return None

        xs: list[float] = []
        ys: list[float] = []
        coords = list(polygon)
        if coords and hasattr(coords[0], "x"):
            for point in coords:
                xs.append(float(point.x))
                ys.append(float(point.y))
        else:
            for index in range(0, len(coords) - 1, 2):
                xs.append(float(coords[index]))
                ys.append(float(coords[index + 1]))

        if not xs or not ys:
            return None

        x_min = min(xs)
        x_max = max(xs)
        y_min = min(ys)
        y_max = max(ys)
        return {
            "x_min": x_min,
            "x_max": x_max,
            "y_min": y_min,
            "y_max": y_max,
            "x_center": (x_min + x_max) / 2,
            "y_center": (y_min + y_max) / 2,
            "height": y_max - y_min,
        }

    def _extract_layout(self, result: Any) -> dict[str, list[dict[str, Any]]]:
        """Serialize Azure line/word geometry for table-style TOTAL extraction."""
        lines: list[dict[str, Any]] = []
        words: list[dict[str, Any]] = []

        for page in getattr(result, "pages", []) or []:
            for line in getattr(page, "lines", []) or []:
                content = getattr(line, "content", "") or ""
                content = re.sub(r"\s+", " ", str(content)).strip()
                if not content:
                    continue
                box = self._polygon_box(getattr(line, "polygon", None))
                lines.append({"content": content, "box": box})

            for word in getattr(page, "words", []) or []:
                content = getattr(word, "content", "") or ""
                content = str(content).strip()
                if not content:
                    continue
                box = self._polygon_box(getattr(word, "polygon", None))
                words.append({"content": content, "box": box})

        return {"lines": lines, "words": words}

    @staticmethod
    def _extract_tables(result: Any) -> list[dict[str, Any]]:
        """Serialize Azure tables into row/column dicts for insurer parsers."""
        tables: list[dict[str, Any]] = []

        for table in getattr(result, "tables", []) or []:
            cells: dict[int, dict[int, str]] = {}
            for cell in getattr(table, "cells", []) or []:
                row_index = getattr(cell, "row_index", None)
                column_index = getattr(cell, "column_index", None)
                if row_index is None or column_index is None:
                    continue
                content = getattr(cell, "content", "") or ""
                cells.setdefault(int(row_index), {})[int(column_index)] = str(content).strip()

            if cells:
                tables.append(cells)

        return tables

    def _enrich_parsed_fields(
        self,
        raw_fields: dict[str, Any],
        confidence_scores: dict[str, float],
        *,
        result: Any | None = None,
        document_type: str = "",
    ) -> dict[str, Any]:
        """Merge insurer-specific and generic parsed values from OCR text."""
        content = raw_fields.get("content")
        text = content if isinstance(content, str) else ""
        layout = self._extract_layout(result) if result is not None else None
        tables = self._extract_tables(result) if result is not None else []

        insurer_parsed = parse_insurance_document(
            text,
            document_type=document_type,
            tables=tables,
        )
        insurer_parsed.pop("_parser_meta", None)

        generic_parsed = parse_invoice_document(
            text,
            existing_fields=raw_fields,
            layout=layout,
        )

        parsed = {**generic_parsed, **insurer_parsed}
        if not parsed:
            return raw_fields

        base_confidence = float(confidence_scores.get("content", 0.75))
        enriched = dict(raw_fields)
        for key, value in parsed.items():
            safe_value = to_json_safe(value)
            if safe_value in (None, ""):
                continue
            enriched[key] = safe_value
            confidence_scores.setdefault(key, base_confidence)
        return enriched

    @staticmethod
    def _field_value(azure_field: Any) -> Any:
        """Resolve the Python value from an Azure document field."""
        if azure_field is None:
            return None

        if isinstance(azure_field, str):
            return azure_field

        value = getattr(azure_field, "value", None)
        if value is not None:
            resolved = AzureInvoiceService._resolve_complex_value(value)
            if resolved is not None:
                return resolved

        for attr in ("value_country", "value_country_region", "value_address"):
            nested = getattr(azure_field, attr, None)
            if nested is None:
                continue
            resolved = AzureInvoiceService._resolve_complex_value(nested)
            if resolved is not None:
                return resolved

        content = getattr(azure_field, "content", None)
        if content is not None:
            return content

        return None

    @staticmethod
    def _resolve_complex_value(value: Any) -> Any:
        """Flatten Azure address/currency objects to a string or number."""
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        if isinstance(value, (int, float, bool)):
            return value

        if isinstance(value, dict):
            for key in ("amount", "code", "content", "value", "currency_symbol"):
                nested = value.get(key)
                if nested is not None and nested != "":
                    if isinstance(nested, (int, float)):
                        return nested
                    if isinstance(nested, str) and nested.strip():
                        return nested.strip()

        for attr in ("amount", "code", "content", "value"):
            nested = getattr(value, attr, None)
            if nested is not None and nested != "":
                if isinstance(nested, (int, float)):
                    return nested
                if isinstance(nested, str) and nested.strip():
                    return nested.strip()

        return None

    @staticmethod
    def _average_word_confidence(result: Any) -> float:
        """Compute mean word confidence across all pages."""
        confidences: list[float] = []
        for page in getattr(result, "pages", []) or []:
            for word in getattr(page, "words", []) or []:
                confidence = getattr(word, "confidence", None)
                if isinstance(confidence, (int, float)):
                    confidences.append(float(confidence))
        if not confidences:
            return 0.0
        return round(sum(confidences) / len(confidences), 4)

"""Azure Document Intelligence client wrapper using Form Recognizer SDK."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, BinaryIO

from django.conf import settings

from apps.ocr.exceptions import AzureOCRError, OCRConfigurationError
from apps.ocr.field_mappings import resolve_model_id
from apps.ocr.serialization import to_json_safe
from apps.ocr.services.driving_license_parser import parse_driving_license_document
from apps.ocr.services.mulkiya_parser import parse_mulkiya_document

logger = logging.getLogger(__name__)


def _normalize_ocr_text(value: str) -> str:
    import re

    return re.sub(r"\s+", " ", value).strip()


@dataclass(frozen=True)
class OCRResult:
    """Normalized OCR output from Azure Document Intelligence."""

    raw_fields: dict[str, Any]
    confidence_scores: dict[str, float]
    model_used: str
    page_count: int
    provider_payload: dict[str, Any] = field(default_factory=dict)


class AzureOCRService:
    """Thin wrapper around ``DocumentAnalysisClient`` for document analysis."""

    def __init__(self) -> None:
        """Load endpoint and key from Django settings."""
        self._endpoint = getattr(settings, "AZURE_FORM_RECOGNIZER_ENDPOINT", "") or ""
        self._key = getattr(settings, "AZURE_FORM_RECOGNIZER_KEY", "") or ""
        self._polling_timeout = int(
            getattr(settings, "OCR_POLLING_TIMEOUT_SECONDS", 120)
        )

    def _get_client(self):
        """Build and return an authenticated Document Analysis client."""
        if not self._endpoint or not self._key:
            raise OCRConfigurationError(
                "Azure Form Recognizer is not configured. Set "
                "AZURE_FORM_RECOGNIZER_ENDPOINT and AZURE_FORM_RECOGNIZER_KEY."
            )

        try:
            from azure.ai.formrecognizer import DocumentAnalysisClient
            from azure.core.credentials import AzureKeyCredential
        except ModuleNotFoundError as exc:
            raise OCRConfigurationError(
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
    ) -> OCRResult:
        """Run Azure analysis and return normalized field output."""
        model_id = resolve_model_id(document_type)
        client = self._get_client()

        try:
            poller = client.begin_analyze_document(model_id, file_obj)
            result = poller.result(timeout=self._polling_timeout)
        except OCRConfigurationError:
            raise
        except Exception as exc:
            logger.exception("Azure OCR failed for document_type=%s", document_type)
            raise AzureOCRError(str(exc)) from exc

        raw_fields, confidence_scores = self._extract_fields(result)
        layout = self._extract_layout(result)
        if layout.get("lines") or layout.get("words"):
            raw_fields["_azure_layout"] = layout
        raw_fields = self._enrich_parsed_fields(
            raw_fields,
            confidence_scores,
            document_type=document_type,
        )
        page_count = len(getattr(result, "pages", []) or [])

        return OCRResult(
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
        """Serialize Azure line/word geometry for label-adjacent field parsing."""
        lines: list[dict[str, Any]] = []
        words: list[dict[str, Any]] = []

        for page in getattr(result, "pages", []) or []:
            for line in getattr(page, "lines", []) or []:
                content = _normalize_ocr_text(getattr(line, "content", "") or "")
                if not content:
                    continue
                box = self._polygon_box(getattr(line, "polygon", None))
                lines.append({"content": content, "box": box})

            for word in getattr(page, "words", []) or []:
                content = _normalize_ocr_text(getattr(word, "content", "") or "")
                if not content:
                    continue
                box = self._polygon_box(getattr(word, "polygon", None))
                words.append({"content": content, "box": box})

        return {"lines": lines, "words": words}

    def _enrich_parsed_fields(
        self,
        raw_fields: dict[str, Any],
        confidence_scores: dict[str, float],
        *,
        document_type: str,
    ) -> dict[str, Any]:
        """Merge regex-parsed values for Emirates ID and Mulkiya uploads."""
        doc_lower = (document_type or "").lower()
        content = raw_fields.get("content")
        text = content if isinstance(content, str) else ""
        parsed: dict[str, Any] = {}

        if "emirates_id" in doc_lower:
            from apps.ocr.services.emirates_id_parser import (
                extract_emirate_from_emirates_id_back,
                extract_emirates_id_number,
                extract_gender_from_emirates_id,
                extract_nationality_from_emirates_id,
            )

            nationality = extract_nationality_from_emirates_id(
                text,
                existing_fields=raw_fields,
            )
            if nationality:
                parsed["nationality"] = nationality
                # Keep Azure key aligned so field_mapper does not prefer Arabic.
                if "Nationality" in raw_fields:
                    parsed["Nationality"] = nationality

            if "emirates_id_front" in doc_lower or doc_lower == "emirates_id":
                emirates_id = extract_emirates_id_number(
                    text,
                    existing_fields=raw_fields,
                )
                if emirates_id:
                    parsed["emirates_id"] = emirates_id
                    if "DocumentNumber" in raw_fields:
                        parsed["DocumentNumber"] = emirates_id

                gender = extract_gender_from_emirates_id(
                    text,
                    existing_fields=raw_fields,
                )
                if gender:
                    parsed["gender"] = gender
                    parsed["Sex"] = gender

            if "emirates_id_back" in doc_lower:
                emirate = extract_emirate_from_emirates_id_back(
                    text,
                    existing_fields=raw_fields,
                )
                if emirate:
                    parsed["emirate"] = emirate
                    if "IssuingPlace" in raw_fields:
                        parsed["IssuingPlace"] = emirate

        if doc_lower in {"driving_license_front", "driving_license"}:
            parsed.update(
                parse_driving_license_document(
                    text,
                    existing_fields=raw_fields,
                    document_type=document_type,
                )
            )

        if "mulkiya" in doc_lower and text.strip():
            parsed.update(
                parse_mulkiya_document(
                    text,
                    document_type=document_type,
                    existing_fields=raw_fields,
                )
            )

        if not parsed:
            return raw_fields

        base_confidence = float(confidence_scores.get("content", 0.75))
        enriched = dict(raw_fields)

        if doc_lower in {"driving_license_front", "driving_license"}:
            if parsed.get("license_no"):
                # DocumentNumber on licenses is the license no, not Emirates ID.
                enriched.pop("DocumentNumber", None)
            if parsed.get("license_from_date"):
                enriched["DateOfIssue"] = parsed["license_from_date"]
                confidence_scores.setdefault("DateOfIssue", base_confidence)
            if parsed.get("license_to_date"):
                enriched["DateOfExpiration"] = parsed["license_to_date"]
                confidence_scores.setdefault("DateOfExpiration", base_confidence)

        for key, value in parsed.items():
            if key in {"document_type"}:
                continue
            safe_value = to_json_safe(value)
            if safe_value in (None, ""):
                continue
            enriched[key] = safe_value
            confidence_scores.setdefault(key, base_confidence)

        if "mulkiya" in doc_lower and parsed.get("plate_source"):
            plate_source = parsed["plate_source"]
            for alias_key in (
                "origin",
                "PlaceOfIssue",
                "place_of_issue",
                "LicensingAuthority",
                "licensing_authority",
                "plate_source",
            ):
                enriched[alias_key] = plate_source
                confidence_scores.setdefault(alias_key, base_confidence)

        if "mulkiya" in doc_lower and parsed.get("plate_code"):
            plate_code = parsed["plate_code"]
            for alias_key in (
                "plate_code",
                "traffic_plate_no",
                "plate_category",
            ):
                enriched[alias_key] = plate_code
                confidence_scores.setdefault(alias_key, base_confidence)

        if "mulkiya" in doc_lower and parsed.get("registration_date"):
            registration_date = parsed["registration_date"]
            for alias_key in (
                "registration_date",
                "RegDate",
                "Reg_Date",
                "reg_date",
            ):
                enriched[alias_key] = registration_date
                confidence_scores.setdefault(alias_key, base_confidence)
            for expiry_key in (
                "expiry_date",
                "ExpiryDate",
                "DateOfExpiration",
                "expiration_date",
                "RegistrationDate",
                "reg_dt",
            ):
                enriched.pop(expiry_key, None)

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
            resolved = AzureOCRService._resolve_complex_value(value)
            if resolved is not None:
                return resolved

        for attr in (
            "value_country",
            "value_country_region",
            "value_address",
        ):
            nested = getattr(azure_field, attr, None)
            if nested is None:
                continue
            resolved = AzureOCRService._resolve_complex_value(nested)
            if resolved is not None:
                return resolved

        content = getattr(azure_field, "content", None)
        if content is not None:
            return content

        return None

    @staticmethod
    def _resolve_complex_value(value: Any) -> Any:
        """Flatten Azure country/address objects to a string."""
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        if isinstance(value, (int, float, bool)):
            return value

        if isinstance(value, dict):
            candidates: list[str] = []
            for key in ("code", "name", "content", "value", "country"):
                nested = value.get(key)
                if isinstance(nested, str) and nested.strip():
                    candidates.append(nested.strip())
            if candidates:
                return AzureOCRService._pick_latin_candidate(candidates)

        dict_attrs: list[str] = []
        for attr in ("code", "name", "content", "value"):
            nested = getattr(value, attr, None)
            if isinstance(nested, str) and nested.strip():
                dict_attrs.append(nested.strip())
        if dict_attrs:
            return AzureOCRService._pick_latin_candidate(dict_attrs)

        return None

    @staticmethod
    def _pick_latin_candidate(candidates: list[str]) -> str | None:
        """Prefer ISO codes and Latin text over Arabic OCR content."""
        import re

        iso = re.compile(r"^[A-Za-z]{2,3}$")
        for candidate in candidates:
            if iso.fullmatch(candidate.strip()):
                return candidate.strip()

        for candidate in candidates:
            letters = [char for char in candidate if char.isalpha()]
            if not letters:
                continue
            latin = len(re.findall(r"[A-Za-z]", candidate))
            if latin / len(letters) >= 0.7:
                return candidate.strip()

        for candidate in candidates:
            if re.search(r"[A-Za-z]", candidate):
                return candidate.strip()

        return candidates[0].strip() if candidates else None

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

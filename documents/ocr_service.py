import logging
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from django.conf import settings

from .models import Document
from .ocr_parser import extract_structured_fields

logger = logging.getLogger(__name__)


class OCRConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class OCRResult:
    provider_response: dict[str, Any]
    ocr_data: dict[str, Any]
    confidence: float
    document_type: str


def _get_azure_client():
    endpoint = getattr(settings, "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", "")
    key = getattr(settings, "AZURE_DOCUMENT_INTELLIGENCE_KEY", "")
    if not endpoint or not key:
        _load_runtime_env()
        endpoint = endpoint or os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", "")
        key = key or os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_KEY", "")
    endpoint = _normalize_endpoint(endpoint)
    key = key.strip().strip('"').strip("'")
    if not endpoint or not key:
        raise OCRConfigurationError(
            "Azure Document Intelligence is not configured. Set "
            "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT and AZURE_DOCUMENT_INTELLIGENCE_KEY."
        )

    try:
        from azure.ai.documentintelligence import DocumentIntelligenceClient
        from azure.core.credentials import AzureKeyCredential
    except ModuleNotFoundError as exc:
        raise OCRConfigurationError(
            "azure-ai-documentintelligence is not installed."
        ) from exc

    return DocumentIntelligenceClient(
        endpoint=endpoint,
        credential=AzureKeyCredential(key),
    )


def _normalize_endpoint(endpoint: str) -> str:
    endpoint = endpoint.strip().strip('"').strip("'")
    parsed = urlparse(endpoint)
    if not parsed.scheme or not parsed.netloc:
        return endpoint.rstrip("/")
    if parsed.path and parsed.path not in ("", "/"):
        logger.warning(
            "Ignoring path component on Azure Document Intelligence endpoint: %s",
            parsed.path,
        )
    return f"{parsed.scheme}://{parsed.netloc}"


def _load_runtime_env() -> None:
    env_path = getattr(settings, "BASE_DIR", None)
    if env_path is None:
        return

    env_file = env_path / ".env"
    if not env_file.exists():
        return

    try:
        from dotenv import load_dotenv

        load_dotenv(env_file)
    except ModuleNotFoundError:
        pass

    for line in env_file.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _average_confidence(result: Any) -> float:
    confidences: list[float] = []
    for page in getattr(result, "pages", []) or []:
        for word in getattr(page, "words", []) or []:
            confidence = getattr(word, "confidence", None)
            if isinstance(confidence, (int, float)):
                confidences.append(float(confidence))
    if not confidences:
        return 0.0
    return round(sum(confidences) / len(confidences), 4)


def run_azure_read_model(document: Document) -> OCRResult:
    if not document.file:
        raise ValueError("Document has no file to process.")

    client = _get_azure_client()
    from azure.ai.documentintelligence.models import AnalyzeDocumentRequest

    timeout = getattr(settings, "DOCUMENT_OCR_POLLING_TIMEOUT_SECONDS", 120)

    document.file.open("rb")
    try:
        poller = client.begin_analyze_document(
            "prebuilt-read",
            body=AnalyzeDocumentRequest(bytes_source=document.file.read()),
        )
        result = poller.result(timeout=timeout)
    finally:
        document.file.close()

    raw_text = getattr(result, "content", "") or ""
    confidence = _average_confidence(result)
    ocr_data = extract_structured_fields(
        raw_text,
        confidence=confidence,
        document_type_hint=document.document_type or "other",
    )
    provider_response = {
        "engine": "azure_document_intelligence",
        "model_id": "prebuilt-read",
        "confidence": confidence,
        "raw_text": raw_text,
        "pages": len(getattr(result, "pages", []) or []),
        "source_file": document.path or document.file.name,
    }

    return OCRResult(
        provider_response=provider_response,
        ocr_data=ocr_data,
        confidence=confidence,
        document_type=ocr_data.get("document_type", document.document_type or "other"),
    )


def process_document_ocr(document_id: int, *, force: bool = False) -> None:
    try:
        document = Document.objects.get(id=document_id)
    except Document.DoesNotExist:
        logger.warning("OCR skipped because document %s no longer exists", document_id)
        return

    if not document.file:
        logger.info("OCR skipped for document %s because no file is attached", document_id)
        return

    source_file = document.path or document.file.name
    existing_source_file = (document.ocr_response or {}).get("source_file")
    if (
        not force
        and document.ocr_status == Document.OCR_SUCCESS
        and existing_source_file == source_file
    ):
        logger.info("OCR skipped for document %s because file was already processed", document_id)
        return

    Document.objects.filter(id=document.id).update(ocr_status=Document.OCR_PENDING)

    try:
        result = run_azure_read_model(document)
    except Exception as exc:
        logger.exception("OCR failed for document %s", document_id)
        Document.objects.filter(id=document.id).update(
            ocr_status=Document.OCR_FAILED,
            status=Document.STATUS_LOW_CONFIDENCE,
            ocr_response={
                "error": str(exc),
                "engine": "azure_document_intelligence",
                "model_id": "prebuilt-read",
                "source_file": source_file,
            },
            ocr_data=None,
            score=0,
        )
        return

    review_status = (
        Document.STATUS_PENDING
        if result.confidence >= getattr(settings, "DOCUMENT_OCR_LOW_CONFIDENCE_THRESHOLD", 0.7)
        else Document.STATUS_LOW_CONFIDENCE
    )
    Document.objects.filter(id=document.id).update(
        ocr_status=Document.OCR_SUCCESS,
        ocr_response=result.provider_response,
        ocr_data=result.ocr_data,
        score=round(result.confidence * 100, 2),
        status=review_status,
    )
    logger.info("OCR completed for document %s", document_id)

"""Deal-specific OCR: parsers, validators, mappers, and extraction pipeline."""

from deals.services.ocr.pipeline import extract_deal_document_from_upload

__all__ = ["extract_deal_document_from_upload"]

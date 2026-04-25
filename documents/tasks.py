import logging
import threading

from django.db import close_old_connections

from .ocr_service import process_document_ocr

logger = logging.getLogger(__name__)


def _run_document_ocr(document_id: int, force: bool) -> None:
    close_old_connections()
    try:
        process_document_ocr(document_id, force=force)
    finally:
        close_old_connections()


def enqueue_document_ocr(document_id: int, *, force: bool = False) -> None:
    thread = threading.Thread(
        target=_run_document_ocr,
        args=(document_id, force),
        name=f"document-ocr-{document_id}",
        daemon=True,
    )
    thread.start()
    logger.info("Queued OCR processing for document %s", document_id)

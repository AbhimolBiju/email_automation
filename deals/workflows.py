import logging

from django.db import transaction

from deals.models import Deal
from documents.models import Document

logger = logging.getLogger(__name__)

REQUIRED_MOTOR_DOCUMENT_TYPES = (
    "mulkiya_id_back",
    "mulkiya_id_front",
    "emirates_id_back",
    "emirates_id_front",
    "driving_license_back",
    "driving_license_front",
)


def maybe_move_deal_to_quotation_after_document_verification(deal_id: int | None) -> bool:
    if not deal_id:
        return False

    with transaction.atomic():
        deal = (
            Deal.objects.select_for_update()
            .select_related("lead")
            .filter(id=deal_id)
            .first()
        )
        if not deal:
            return False

        if deal.stage_id != Deal.STAGE_AWAITING_ADDITIONAL_DOCUMENTS:
            return False

        latest_documents_by_type: dict[str, Document] = {}
        latest_documents = (
            Document.objects.filter(
                motor_deal_id=deal.id,
                document_type__in=REQUIRED_MOTOR_DOCUMENT_TYPES,
            )
            .only("id", "document_type", "status", "uploaded_at")
            .order_by("document_type", "-uploaded_at", "-id")
        )

        for document in latest_documents:
            latest_documents_by_type.setdefault(document.document_type, document)

        if len(latest_documents_by_type) != len(REQUIRED_MOTOR_DOCUMENT_TYPES):
            return False

        if any(
            latest_documents_by_type[document_type].status != Document.STATUS_VERIFIED
            for document_type in REQUIRED_MOTOR_DOCUMENT_TYPES
        ):
            return False

        updated = Deal.objects.filter(
            id=deal.id,
            stage_id=Deal.STAGE_AWAITING_ADDITIONAL_DOCUMENTS,
        ).update(stage_id=Deal.STAGE_QUOTATION)

        if not updated:
            return False

        logger.info(
            "Deal #%s moved from Awaiting Additional Documents to Quotation after all required motor docs verified.",
            deal.id,
        )
        from insurance.tasks import enqueue_quote_generation

        transaction.on_commit(
            lambda: enqueue_quote_generation(
                deal.id,
                force_refresh=True,
            )
        )
        return True

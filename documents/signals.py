from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from deals.workflows import maybe_move_deal_to_quotation_after_document_verification
from .models import Document
from .tasks import enqueue_document_ocr


@receiver(pre_save, sender=Document)
def remember_previous_file(sender, instance: Document, **kwargs):
    if not instance.pk:
        instance._previous_file_name = None
        instance._previous_status = None
        return

    previous = sender.objects.filter(pk=instance.pk).values("file", "status").first() or {}
    instance._previous_file_name = previous.get("file")
    instance._previous_status = previous.get("status")


@receiver(post_save, sender=Document)
def trigger_ocr_after_upload(sender, instance: Document, created: bool, **kwargs):
    if not getattr(settings, "DOCUMENT_OCR_AUTO_PROCESS", True):
        return
    if not instance.file:
        return

    previous_file_name = getattr(instance, "_previous_file_name", None)
    current_file_name = instance.file.name
    file_changed = previous_file_name is not None and previous_file_name != current_file_name
    if not created and not file_changed:
        return

    transaction.on_commit(lambda: enqueue_document_ocr(instance.id, force=file_changed))


@receiver(post_save, sender=Document)
def maybe_advance_motor_deal_after_document_changes(
    sender,
    instance: Document,
    created: bool,
    **kwargs,
):
    if not instance.motor_deal_id:
        return

    previous_status = getattr(instance, "_previous_status", None)
    should_check = created or (
        previous_status != Document.STATUS_VERIFIED
        and instance.status == Document.STATUS_VERIFIED
    )
    if not should_check:
        return

    transaction.on_commit(
        lambda: maybe_move_deal_to_quotation_after_document_verification(
            instance.motor_deal_id
        )
    )


@receiver(post_delete, sender=Document)
def recheck_motor_deal_after_document_delete(sender, instance: Document, **kwargs):
    if not instance.motor_deal_id:
        return

    transaction.on_commit(
        lambda: maybe_move_deal_to_quotation_after_document_verification(
            instance.motor_deal_id
        )
    )

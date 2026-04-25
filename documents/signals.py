from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Document
from .tasks import enqueue_document_ocr


@receiver(pre_save, sender=Document)
def remember_previous_file(sender, instance: Document, **kwargs):
    if not instance.pk:
        instance._previous_file_name = None
        return

    previous = sender.objects.filter(pk=instance.pk).values_list("file", flat=True).first()
    instance._previous_file_name = previous


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

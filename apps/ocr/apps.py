from django.apps import AppConfig


class OcrConfig(AppConfig):
    """Django app configuration for the OCR microservice."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ocr"
    label = "apps_ocr"
    verbose_name = "OCR"

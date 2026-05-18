from django.apps import AppConfig


class InvoiceConfig(AppConfig):
    """Django app configuration for the invoice extraction microservice."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.invoice"
    label = "apps_invoice"
    verbose_name = "Invoice"

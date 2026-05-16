"""URL routes for the OCR microservice."""

from django.urls import path

from apps.ocr import views

urlpatterns = [
    path("extract/", views.extract_document, name="ocr-extract"),
]

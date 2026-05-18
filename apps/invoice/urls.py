"""URL routes for the invoice extraction microservice."""

from django.urls import path

from apps.invoice import views

urlpatterns = [
    path("extract/", views.extract_document, name="invoice-extract"),
    path("jobs/<int:job_id>/", views.get_job, name="invoice-job-detail"),
]

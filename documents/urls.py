from django.urls import path
from .views import *

urlpatterns = [
     path("status/",ocr_stats),
     path('upload/', upload_ocr_document),
         path("documents/", document_list),
         path("<id>/details/", document_detail),
         path("<id>/verify/", verify_document),
         path("<id>/reject/", reject_document),
]
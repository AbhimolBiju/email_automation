from django.contrib import admin
from .models import Document, OCRDocument
# Register your models here.

admin.site.register(Document)
admin.site.register(OCRDocument)

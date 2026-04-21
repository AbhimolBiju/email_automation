from django.contrib import admin
from .models import QuoteRequest,Insurer

# Register your models here.
admin.site.register(QuoteRequest)
admin.site.register(Insurer)
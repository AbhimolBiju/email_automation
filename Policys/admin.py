from django.contrib import admin
from .models import Policy,PolicyInsurer,AdditionalDocument

# Register your models here.
admin.site.register(Policy)
admin.site.register(PolicyInsurer)
admin.site.register(AdditionalDocument)
from django.contrib import admin
from .models import Policy,PolicyInsurer

# Register your models here.
admin.site.register(Policy)
admin.site.register(PolicyInsurer)
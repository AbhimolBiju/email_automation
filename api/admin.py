from django.contrib import admin
from .models import CustomUser

from invoice.models import Transaction,Invoice
# Register your models here.
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'mobile', 'role']
    list_editable = ['mobile', 'role']


admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Transaction)
admin.site.register(Invoice)

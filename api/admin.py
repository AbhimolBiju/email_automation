from django.contrib import admin
from .models import Profile, Role
from invoice.models import Transaction,Invoice
# Register your models here.
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role']
    list_editable = ['role']   # allows inline editing


admin.site.register(Profile, ProfileAdmin)
admin.site.register(Role)
admin.site.register(Transaction)
admin.site.register(Invoice)
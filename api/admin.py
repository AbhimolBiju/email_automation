from django.contrib import admin
from .models import CustomUser
# Register your models here.
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'mobile', 'role']
    list_editable = ['mobile', 'role']


admin.site.register(CustomUser, CustomUserAdmin)

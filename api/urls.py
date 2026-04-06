"""
URL configuration for crm_pro project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.urls import path
from .views import *

urlpatterns = [
    path("test/",test_api),
    path('register/', register_user),
    path('login/', login_user),
    path('logout/', logout_user),
    path('protected/', protected_view),
    path('update-user/<int:user_id>/', update_user_role),
    path('roles/',list_roles),
    path('manager-dashboard/', manager_dashboard),
]

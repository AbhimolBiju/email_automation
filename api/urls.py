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

from django.urls import include, path
from .views import *
from .token_views import CookieTokenRefreshView

urlpatterns = [
    path("ocr/", include("apps.ocr.urls")),
    path("invoice/", include("apps.invoice.urls")),
    path("auth/token/refresh/", CookieTokenRefreshView.as_view(), name="token_refresh"),
    path("test/",test_api),
    path('register/step1/', register_step1),
    path('register/step2/', register_step2),
    path('login/', login_user),
    path('logout/', logout_user),
    path('protected/', protected_view),
    path('user_profile/', user_profile),
    path("users/create/", CreateUserView.as_view(), name="create-user"),
    path('users/list/', UserListView.as_view()),
    path('users/update/<int:id>/', update_user),
    path('users/update-role/<int:pk>/', UpdateUserRoleView.as_view()),
    path("users/<int:pk>/toggle-active/",ToggleUserActiveAPIView.as_view(),name="toggle-user-active"),

    path('profile/',ProfileView.as_view(),name='profile'),

    path('profile/update/',ProfileUpdateView.as_view(),name='profile-update'),

    # path('profile/upload-picture/',ProfilePictureUploadView.as_view(),name='upload-picture'),
  
    path("dashboard/stats/", DashboardStatsView.as_view()),
    path("dashboard/sales-trend/", SalesTrendView.as_view()),
    path("dashboard/product-mix/", ProductMixView.as_view()),
    path("dashboard/revenue-trend/", RevenueTrendView.as_view()),
    path("dashboard/conversion/", ConversionFunnelView.as_view()),
    path("dashboard/renewals/", RevenueTrendView.as_view()),
]

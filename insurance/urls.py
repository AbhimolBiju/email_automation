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
from .policy_issuance_views import policy_issuance_detail, policy_issuances
from .qic_api_views import VehicleLookupView
from .views import *

urlpatterns = [
    path("general-info/<int:lead_id>/", get_insurance_info),
    path("providers/", list_insurance_providers),
    path("providers/<int:provider_id>/health-check/", provider_health_check),
    path("deals/<int:deal_id>/quotes/", get_deal_quotes),
    path("deals/<int:deal_id>/compare-quotes/", compare_quotes),

    
    path("dic/", include("insurance.dic_urls")),
    path("qic/", include("insurance.qic_urls")),
    path("nia/", include("insurance.nia_url")),
    
    path("policy-issuances/", policy_issuances),
    path("policy-issuances/<int:pk>/", policy_issuance_detail),
    path("quotes/", list_quotes),
    path("quotes/<int:batch_id>/", quote_batch_detail),
    path("quotes/<int:batch_id>/results/", quote_batch_results),
    path("quotes/deal/<int:deal_id>/latest/", latest_quote_for_deal),
    path("quotes/batch/<int:batch_id>/refresh/", refresh_quote_batch_view),
    path("vehicle/lookup/", VehicleLookupView.as_view()),
]



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
    # POST create — must be before "" so "" is not mistaken for "create"
    path("create/", create_lead, name="create"),
    # GET list all leads at GET /leads/ (was incorrectly only under /leads/export/)
    path("export/", lead_list, name="lead_list_export"),
    path('<int:lead_id>/status/', update_lead_status),
    path('<int:lead_id>/', lead_details),
    path('<int:lead_id>/stage/', update_lead_stage),
    path('<int:lead_id>/activities/create/', create_activity),
    path('<int:lead_id>/activities/', lead_activities),
    path('<int:id>/favorite/', ToggleFavoriteView.as_view(), name='toggle-favorite'),
    # path("<int:lead_id>/tasks/",create_task),
    # path("insurance/general-info/<int:lead_id>/",get_insurance_info),
    # GET list (keep last so "" does not capture numeric paths)
    path("", lead_list, name="lead_list"),
    path("StatsView/",StatsView.as_view(), name="StatsView"),
]




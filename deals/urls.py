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
    path('create_deal/', create_deal, name='create-deal'),
    path('documents/upload/', upload_deal_document, name='upload-deal-document'),
    path('<int:deal_id>/', deal_detail, name='deal-detail'),
    path('pipeline-summary/', pipeline_summary, name='pipeline-summary'),
    path('board/', deals_board, name='deals-board'),
    path('search/', search_deals, name='search-deals'),
    path('<int:id>/move/', update_deal_stage, name='update-deal-stage'),
    path('export/', export_deals, name='export-deals'),
    path('dashboard/stage-deals/', deals_by_stage, name='deals-by-stage'),
    path('filter-options/', deal_filter_options, name='deal-filter-options'),
    path('list/', deal_list, name='deal-list'),
    path('deals_board_paginated/', deals_board_paginated, name='deals-board-paginated'),
    path('grouped_deals/', grouped_deals, name='grouped-deals'),
    path('<int:deal_id>/deal_underwriter_information/', deal_underwriter_information, name='deal-general-info'),
    path('<int:deal_id>/update-additional-field/', update_additional_field, name='update-additional-field'),
    
    
]

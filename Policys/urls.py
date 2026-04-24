from django.urls import path
from .views import *

urlpatterns = [
    path('policy-queue/', PolicyQueueView, name='policy-queue'),
    path('policy-status/<int:pk>/', update_policy_status, name='update-policy-status'),
    path('view-quote/<int:pk>/', view_quote,name="policy_quote"),
    path('policy_status/',policy_stats,name="policy_stats")
]
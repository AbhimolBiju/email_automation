from django.urls import path
from .views import (
    QuoteRequestCreateView,
    QuoteRequestListView,
    QuoteRequestDetailView,
    QuoteComparisonView,
    QuoteStatsView,
    
)

urlpatterns = [
    path('quotes/', QuoteRequestListView.as_view()),
    path('quotes/stats', QuoteStatsView.as_view()),
    path('quotes/create/', QuoteRequestCreateView.as_view()),
path('quotes/<int:quote_id>/', QuoteRequestDetailView.as_view()),
    path('quotes/<int:quote_id>/comparison/', QuoteComparisonView.as_view()),
]
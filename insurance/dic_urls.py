from django.urls import path

from .dic_api_views import (
    DICAuthenticateView,
    DICChooseSchemeView,
    DICDownloadPolicyDocumentsView,
    DICFetchPolicyView,
    DICGenerateQuoteView,
    DICGetQuoteView,
    DICHealthCheckView,
    DICMasterdataView,
    DICPaymentInfoView,
    DICSupportedMasterdataView,
    DICIssuePolicyView,
)


urlpatterns = [
    path("health-check/", DICHealthCheckView.as_view()),
    path("authenticate/", DICAuthenticateView.as_view()),
    path("masterdata/", DICSupportedMasterdataView.as_view()),
    path("masterdata/<str:dataset>/", DICMasterdataView.as_view()),
    path("generate-quote/", DICGenerateQuoteView.as_view()),
    path("choose-scheme/", DICChooseSchemeView.as_view()),
    path("payment-info/", DICPaymentInfoView.as_view()),
    path("quote/", DICGetQuoteView.as_view()),
    path("issue-policy/", DICIssuePolicyView.as_view()),
    path("fetch-policy/", DICFetchPolicyView.as_view()),
    path("download-policy-documents/", DICDownloadPolicyDocumentsView.as_view()),
]


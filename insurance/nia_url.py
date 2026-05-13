from django.urls import path

from .nia_api_views import (
    NIAApprovePolicyView,
    NIAAuthenticateView,
    NIACreateQuoteView,
    NIAFetchPolicyView,
    NIAGeneratePaymentLinkView,
    NIAGetPaymentDetailsView,
    NIAGetQuoteView,
    NIAHealthCheckView,
    NIAIssuePolicyView,
    NIAProposalSummaryView,
    NIARenewPolicyView,
    NIASaveAdditionalInfoView,
    NIASaveDocumentsView,
    NIASaveQuoteWithPlanView,
)


urlpatterns = [
    path("health-check/", NIAHealthCheckView.as_view()),
    path("authenticate/", NIAAuthenticateView.as_view()),
    path("create-quote/", NIACreateQuoteView.as_view()),
    path("save-quote-with-plan/", NIASaveQuoteWithPlanView.as_view()),
    path("save-additional-info/", NIASaveAdditionalInfoView.as_view()),
    path("save-documents/", NIASaveDocumentsView.as_view()),
    path("proposal-summary/", NIAProposalSummaryView.as_view()),
    path("approve-policy/", NIAApprovePolicyView.as_view()),
    path("generate-payment-link/", NIAGeneratePaymentLinkView.as_view()),
    path("payment-details/", NIAGetPaymentDetailsView.as_view()),
    path("quote/", NIAGetQuoteView.as_view()),
    path("issue-policy/", NIAIssuePolicyView.as_view()),
    path("renew-policy/", NIARenewPolicyView.as_view()),
    path("fetch-policy/", NIAFetchPolicyView.as_view()),
]
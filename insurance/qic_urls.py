from django.urls import path

from .qic_api_views import (
    QICAuthenticateView,
    QICBayanatyBodyTypeView,
    QICBayanatyEngineCapacitiesView,
    QICBayanatyImportedDetailsView,
    QICBayanatyTrimsView,
    QICBayanatyVehicleDetailsView,
    QICBayanatyVehicleSpecView,
    QICBayanatyVehicleValuationView,
    QICDownloadDocumentsView,
    QICDownloadQuoteDocumentView,
    QICFetchPolicyView,
    QICGetNetPremiumView,
    QICGetQuoteView,
    QICGetTariffView,
    QICHealthCheckView,
    QICIssuePolicyView,
    QICRenewPolicyView,
    QICSendPaymentLinkView,
)


urlpatterns = [
    path("health-check/", QICHealthCheckView.as_view()),
    path("authenticate/", QICAuthenticateView.as_view()),
    path("tariff/", QICGetTariffView.as_view()),
    path("net-premium/", QICGetNetPremiumView.as_view()),
    path("send-payment-link/", QICSendPaymentLinkView.as_view()),
    path("download-quote-document/", QICDownloadQuoteDocumentView.as_view()),
    path("download-documents/", QICDownloadDocumentsView.as_view()),
    path("fetch-policy/", QICFetchPolicyView.as_view()),
    path("quote/", QICGetQuoteView.as_view()),
    path("issue-policy/", QICIssuePolicyView.as_view()),
    path("renew-policy/", QICRenewPolicyView.as_view()),
    path("bayanaty/vehicle-details/", QICBayanatyVehicleDetailsView.as_view()),
    path("bayanaty/imported-details/", QICBayanatyImportedDetailsView.as_view()),
    path("bayanaty/vehicle-spec/", QICBayanatyVehicleSpecView.as_view()),
    path("bayanaty/vehicle-valuation/", QICBayanatyVehicleValuationView.as_view()),
    path("bayanaty/body-type/", QICBayanatyBodyTypeView.as_view()),
    path("bayanaty/engine-capacities/", QICBayanatyEngineCapacitiesView.as_view()),
    path("bayanaty/trims/", QICBayanatyTrimsView.as_view()),
]

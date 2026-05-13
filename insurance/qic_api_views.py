from __future__ import annotations

from typing import Any

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from api.responses import error_response, success_response
from insurance.models import InsuranceProvider
from insurance.providers import build_provider
from insurance.providers.exceptions import InsuranceProviderError
from insurance.providers.qic_provider import QICProvider

from .qic_api_serializers import (
    QICDownloadQuoteDocumentSerializer,
    QICLoosePayloadSerializer,
    QICVinRequestSerializer,
)


def _get_qic_provider() -> QICProvider:
    try:
        config = InsuranceProvider.objects.get(code__iexact="QIC", is_active=True)
    except InsuranceProvider.DoesNotExist as exc:
        raise LookupError("QIC provider is not configured or not active.") from exc
    provider = build_provider(config)
    if not isinstance(provider, QICProvider):
        raise TypeError("Configured QIC provider_class is not QICProvider.")
    return provider


def _validate_payload(request) -> dict[str, Any] | None:
    serializer = QICLoosePayloadSerializer(data=request.data)
    if serializer.is_valid():
        return serializer.validated_data
    return None


class QICHealthCheckView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            provider = _get_qic_provider()
            data = provider.health_check()
        except LookupError as exc:
            return error_response(
                message=str(exc),
                code=status.HTTP_404_NOT_FOUND,
                errors={"provider": ["QIC not available"]},
            )
        except InsuranceProviderError as exc:
            return error_response(
                message="QIC health check failed",
                code=status.HTTP_503_SERVICE_UNAVAILABLE,
                errors={"detail": str(exc)},
            )
        return success_response(message="QIC health check completed", data=data)


class QICAuthenticateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            provider = _get_qic_provider()
            token = provider.authenticate()
        except LookupError as exc:
            return error_response(
                message=str(exc),
                code=status.HTTP_404_NOT_FOUND,
                errors={"provider": ["QIC not available"]},
            )
        except InsuranceProviderError as exc:
            return error_response(
                message="QIC authentication failed",
                code=status.HTTP_401_UNAUTHORIZED,
                errors={"detail": str(exc)},
            )
        return success_response(message="QIC authenticated successfully", data={"token": token})


class QICGetTariffView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payload = _validate_payload(request)
        if payload is None:
            return error_response(
                message="Invalid request payload",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": ["Expected a JSON object."]},
            )
        try:
            provider = _get_qic_provider()
            data = provider.get_tariff(payload)
        except LookupError as exc:
            return error_response(
                message=str(exc),
                code=status.HTTP_404_NOT_FOUND,
                errors={"provider": ["QIC not available"]},
            )
        except InsuranceProviderError as exc:
            return error_response(
                message="QIC tariff request failed",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": str(exc)},
            )
        return success_response(message="QIC tariff fetched successfully", data=data)


class QICGetNetPremiumView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payload = _validate_payload(request)
        if payload is None:
            return error_response(
                message="Invalid request payload",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": ["Expected a JSON object."]},
            )
        try:
            provider = _get_qic_provider()
            data = provider.get_net_premium(payload)
        except LookupError as exc:
            return error_response(
                message=str(exc),
                code=status.HTTP_404_NOT_FOUND,
                errors={"provider": ["QIC not available"]},
            )
        except InsuranceProviderError as exc:
            return error_response(
                message="QIC net premium request failed",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": str(exc)},
            )
        return success_response(message="QIC net premium fetched successfully", data=data)


class QICSendPaymentLinkView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payload = _validate_payload(request)
        if payload is None:
            return error_response(
                message="Invalid request payload",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": ["Expected a JSON object."]},
            )
        try:
            provider = _get_qic_provider()
            data = provider.send_payment_link(payload)
        except LookupError as exc:
            return error_response(
                message=str(exc),
                code=status.HTTP_404_NOT_FOUND,
                errors={"provider": ["QIC not available"]},
            )
        except InsuranceProviderError as exc:
            return error_response(
                message="QIC payment link request failed",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": str(exc)},
            )
        return success_response(message="QIC payment link sent successfully", data=data)


class QICDownloadQuoteDocumentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = QICDownloadQuoteDocumentSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                message="Invalid request payload",
                code=status.HTTP_400_BAD_REQUEST,
                errors=serializer.errors,
            )
        validated_data = serializer.validated_data
        try:
            provider = _get_qic_provider()
            data = provider.download_quote_document(
                quote_no=validated_data["quote_no"],
                doc_type=validated_data.get("doc_type", "Quotation"),
            )
        except LookupError as exc:
            return error_response(
                message=str(exc),
                code=status.HTTP_404_NOT_FOUND,
                errors={"provider": ["QIC not available"]},
            )
        except InsuranceProviderError as exc:
            return error_response(
                message="QIC quote document download failed",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": str(exc)},
            )
        return success_response(message="QIC quote document fetched successfully", data=data)


class QICDownloadDocumentsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payload = _validate_payload(request)
        if payload is None:
            return error_response(
                message="Invalid request payload",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": ["Expected a JSON object."]},
            )
        try:
            provider = _get_qic_provider()
            data = provider.download_documents(payload)
        except LookupError as exc:
            return error_response(
                message=str(exc),
                code=status.HTTP_404_NOT_FOUND,
                errors={"provider": ["QIC not available"]},
            )
        except InsuranceProviderError as exc:
            return error_response(
                message="QIC document download failed",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": str(exc)},
            )
        return success_response(message="QIC policy documents fetched successfully", data=data)


class QICFetchPolicyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payload = _validate_payload(request)
        if payload is None:
            return error_response(
                message="Invalid request payload",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": ["Expected a JSON object."]},
            )
        try:
            provider = _get_qic_provider()
            data = provider.fetch_policy(payload)
        except LookupError as exc:
            return error_response(
                message=str(exc),
                code=status.HTTP_404_NOT_FOUND,
                errors={"provider": ["QIC not available"]},
            )
        except InsuranceProviderError as exc:
            return error_response(
                message="QIC fetch policy failed",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": str(exc)},
            )
        return success_response(message="QIC policy fetched successfully", data=data)


class QICGetQuoteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payload = _validate_payload(request)
        if payload is None:
            return error_response(
                message="Invalid request payload",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": ["Expected a JSON object."]},
            )
        try:
            provider = _get_qic_provider()
            normalized = provider.get_quote(payload)
        except LookupError as exc:
            return error_response(
                message=str(exc),
                code=status.HTTP_404_NOT_FOUND,
                errors={"provider": ["QIC not available"]},
            )
        except InsuranceProviderError as exc:
            return error_response(
                message="QIC quote failed",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": str(exc)},
            )
        return success_response(message="QIC quote fetched successfully", data=normalized.as_dict())


class QICIssuePolicyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payload = _validate_payload(request)
        if payload is None:
            return error_response(
                message="Invalid request payload",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": ["Expected a JSON object."]},
            )
        try:
            provider = _get_qic_provider()
            data = provider.issue_policy(payload)
        except LookupError as exc:
            return error_response(
                message=str(exc),
                code=status.HTTP_404_NOT_FOUND,
                errors={"provider": ["QIC not available"]},
            )
        except InsuranceProviderError as exc:
            return error_response(
                message="QIC issue policy failed",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": str(exc)},
            )
        return success_response(message="QIC policy issue info fetched successfully", data=data)


class QICRenewPolicyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payload = _validate_payload(request)
        if payload is None:
            return error_response(
                message="Invalid request payload",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": ["Expected a JSON object."]},
            )
        try:
            provider = _get_qic_provider()
            data = provider.renew_policy(payload)
        except LookupError as exc:
            return error_response(
                message=str(exc),
                code=status.HTTP_404_NOT_FOUND,
                errors={"provider": ["QIC not available"]},
            )
        except InsuranceProviderError as exc:
            return error_response(
                message="QIC renew policy failed",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": str(exc)},
            )
        return success_response(message="QIC policy renewal quote fetched successfully", data=data)


class QICBayanatyVehicleDetailsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = QICVinRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                message="Invalid request payload",
                code=status.HTTP_400_BAD_REQUEST,
                errors=serializer.errors,
            )
        try:
            provider = _get_qic_provider()
            data = provider.bayanaty_vehicle_details(vin=serializer.validated_data["vin"])
        except LookupError as exc:
            return error_response(
                message=str(exc),
                code=status.HTTP_404_NOT_FOUND,
                errors={"provider": ["QIC not available"]},
            )
        except InsuranceProviderError as exc:
            return error_response(
                message="QIC Bayanaty vehicle details failed",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": str(exc)},
            )
        return success_response(message="QIC Bayanaty vehicle details fetched successfully", data=data)


class QICBayanatyImportedDetailsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = QICVinRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                message="Invalid request payload",
                code=status.HTTP_400_BAD_REQUEST,
                errors=serializer.errors,
            )
        try:
            provider = _get_qic_provider()
            data = provider.bayanaty_imported_details(vin=serializer.validated_data["vin"])
        except LookupError as exc:
            return error_response(
                message=str(exc),
                code=status.HTTP_404_NOT_FOUND,
                errors={"provider": ["QIC not available"]},
            )
        except InsuranceProviderError as exc:
            return error_response(
                message="QIC Bayanaty imported details failed",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": str(exc)},
            )
        return success_response(message="QIC Bayanaty imported details fetched successfully", data=data)


class QICBayanatyVehicleSpecView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = QICVinRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                message="Invalid request payload",
                code=status.HTTP_400_BAD_REQUEST,
                errors=serializer.errors,
            )
        try:
            provider = _get_qic_provider()
            data = provider.bayanaty_vehicle_spec(vin=serializer.validated_data["vin"])
        except LookupError as exc:
            return error_response(
                message=str(exc),
                code=status.HTTP_404_NOT_FOUND,
                errors={"provider": ["QIC not available"]},
            )
        except InsuranceProviderError as exc:
            return error_response(
                message="QIC Bayanaty vehicle spec failed",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": str(exc)},
            )
        return success_response(message="QIC Bayanaty vehicle spec fetched successfully", data=data)


class QICBayanatyVehicleValuationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payload = _validate_payload(request)
        if payload is None:
            return error_response(
                message="Invalid request payload",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": ["Expected a JSON object."]},
            )
        try:
            provider = _get_qic_provider()
            data = provider.bayanaty_vehicle_valuation(payload)
        except LookupError as exc:
            return error_response(
                message=str(exc),
                code=status.HTTP_404_NOT_FOUND,
                errors={"provider": ["QIC not available"]},
            )
        except InsuranceProviderError as exc:
            return error_response(
                message="QIC Bayanaty vehicle valuation failed",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": str(exc)},
            )
        return success_response(message="QIC Bayanaty vehicle valuation fetched successfully", data=data)


class QICBayanatyBodyTypeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payload = _validate_payload(request)
        if payload is None:
            return error_response(
                message="Invalid request payload",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": ["Expected a JSON object."]},
            )
        try:
            provider = _get_qic_provider()
            data = provider.bayanaty_body_type(payload)
        except LookupError as exc:
            return error_response(
                message=str(exc),
                code=status.HTTP_404_NOT_FOUND,
                errors={"provider": ["QIC not available"]},
            )
        except InsuranceProviderError as exc:
            return error_response(
                message="QIC Bayanaty body type failed",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": str(exc)},
            )
        return success_response(message="QIC Bayanaty body type fetched successfully", data=data)


class QICBayanatyEngineCapacitiesView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payload = _validate_payload(request)
        if payload is None:
            return error_response(
                message="Invalid request payload",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": ["Expected a JSON object."]},
            )
        try:
            provider = _get_qic_provider()
            data = provider.bayanaty_engine_capacities(payload)
        except LookupError as exc:
            return error_response(
                message=str(exc),
                code=status.HTTP_404_NOT_FOUND,
                errors={"provider": ["QIC not available"]},
            )
        except InsuranceProviderError as exc:
            return error_response(
                message="QIC Bayanaty engine capacities failed",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": str(exc)},
            )
        return success_response(message="QIC Bayanaty engine capacities fetched successfully", data=data)


class QICBayanatyTrimsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payload = _validate_payload(request)
        if payload is None:
            return error_response(
                message="Invalid request payload",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": ["Expected a JSON object."]},
            )
        try:
            provider = _get_qic_provider()
            data = provider.bayanaty_trims(payload)
        except LookupError as exc:
            return error_response(
                message=str(exc),
                code=status.HTTP_404_NOT_FOUND,
                errors={"provider": ["QIC not available"]},
            )
        except InsuranceProviderError as exc:
            return error_response(
                message="QIC Bayanaty trims failed",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": str(exc)},
            )
        return success_response(message="QIC Bayanaty trims fetched successfully", data=data)
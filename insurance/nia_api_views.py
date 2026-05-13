from __future__ import annotations

import logging
from typing import Any

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from api.responses import error_response, success_response
from insurance.models import InsuranceProvider
from insurance.providers import build_provider
from insurance.providers.exceptions import InsuranceProviderError
from insurance.providers.nia_provider import NIAProvider

from .nia_api_serializers import NIALoosePayloadSerializer

logger = logging.getLogger(__name__)


def _get_nia_provider() -> NIAProvider:
    try:
        config = InsuranceProvider.objects.get(code__iexact="NIA", is_active=True)
    except InsuranceProvider.DoesNotExist as exc:
        raise LookupError("NIA provider is not configured or not active.") from exc
    provider = build_provider(config)
    if not isinstance(provider, NIAProvider):
        raise TypeError("Configured NIA provider_class is not NIAProvider.")
    return provider


def _validate_payload(request) -> dict[str, Any] | None:
    serializer = NIALoosePayloadSerializer(data=request.data)
    if serializer.is_valid():
        return serializer.validated_data
    return None


class NIAHealthCheckView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            provider = _get_nia_provider()
            data = provider.health_check()
        except LookupError as exc:
            return error_response(
                message=str(exc),
                code=status.HTTP_404_NOT_FOUND,
                errors={"provider": ["NIA not available"]},
            )
        except InsuranceProviderError as exc:
            return error_response(
                message="NIA health check failed",
                code=status.HTTP_503_SERVICE_UNAVAILABLE,
                errors={"detail": str(exc)},
            )
        return success_response(message="NIA health check completed", data=data)


class NIAAuthenticateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            provider = _get_nia_provider()
            token = provider.authenticate()
        except LookupError as exc:
            return error_response(
                message=str(exc),
                code=status.HTTP_404_NOT_FOUND,
                errors={"provider": ["NIA not available"]},
            )
        except InsuranceProviderError as exc:
            return error_response(
                message="NIA authentication failed",
                code=status.HTTP_401_UNAUTHORIZED,
                errors={"detail": str(exc)},
            )
        return success_response(message="NIA authenticated successfully", data={"token": token})


class NIACreateQuoteView(APIView):
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
            provider = _get_nia_provider()
            data = provider.create_quote(payload)
        except LookupError as exc:
            return error_response(
                message=str(exc),
                code=status.HTTP_404_NOT_FOUND,
                errors={"provider": ["NIA not available"]},
            )
        except InsuranceProviderError as exc:
            return error_response(
                message="NIA create quote failed",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": str(exc)},
            )
        return success_response(message="NIA quote created successfully", data=data)


class NIASaveQuoteWithPlanView(APIView):
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
            provider = _get_nia_provider()
            data = provider.save_quote_with_plan(payload)
        except LookupError as exc:
            return error_response(
                message=str(exc),
                code=status.HTTP_404_NOT_FOUND,
                errors={"provider": ["NIA not available"]},
            )
        except InsuranceProviderError as exc:
            return error_response(
                message="NIA save quote with plan failed",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": str(exc)},
            )
        return success_response(message="NIA quote plan saved successfully", data=data)


class NIASaveAdditionalInfoView(APIView):
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
            provider = _get_nia_provider()
            data = provider.save_additional_info(payload)
        except LookupError as exc:
            return error_response(
                message=str(exc),
                code=status.HTTP_404_NOT_FOUND,
                errors={"provider": ["NIA not available"]},
            )
        except InsuranceProviderError as exc:
            return error_response(
                message="NIA save additional info failed",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": str(exc)},
            )
        return success_response(message="NIA additional info saved successfully", data=data)


class NIASaveDocumentsView(APIView):
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
            provider = _get_nia_provider()
            data = provider.save_documents(payload)
        except LookupError as exc:
            return error_response(
                message=str(exc),
                code=status.HTTP_404_NOT_FOUND,
                errors={"provider": ["NIA not available"]},
            )
        except InsuranceProviderError as exc:
            return error_response(
                message="NIA save documents failed",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": str(exc)},
            )
        return success_response(message="NIA documents saved successfully", data=data)


class NIAProposalSummaryView(APIView):
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
            logger.info(
                "[NIA proposal-summary] incoming keys=%s candidate_values=%s",
                sorted(list(payload.keys())),
                {
                    "PolRefNo": payload.get("PolRefNo"),
                    "quotation_no": payload.get("quotation_no"),
                    "QuotNo": payload.get("QuotNo"),
                    "polRefNo": payload.get("polRefNo"),
                    "reference_no": payload.get("reference_no"),
                    "quote_no": payload.get("quote_no"),
                },
            )
            provider = _get_nia_provider()
            data = provider.proposal_summary(payload)
        except LookupError as exc:
            return error_response(
                message=str(exc),
                code=status.HTTP_404_NOT_FOUND,
                errors={"provider": ["NIA not available"]},
            )
        except InsuranceProviderError as exc:
            return error_response(
                message="NIA proposal summary failed",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": str(exc)},
            )
        return success_response(message="NIA proposal summary fetched successfully", data=data)


class NIAApprovePolicyView(APIView):
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
            provider = _get_nia_provider()
            data = provider.approve_policy(payload)
        except LookupError as exc:
            return error_response(
                message=str(exc),
                code=status.HTTP_404_NOT_FOUND,
                errors={"provider": ["NIA not available"]},
            )
        except InsuranceProviderError as exc:
            return error_response(
                message="NIA approve policy failed",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": str(exc)},
            )
        return success_response(message="NIA policy approved successfully", data=data)


class NIAGeneratePaymentLinkView(APIView):
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
            provider = _get_nia_provider()
            data = provider.generate_payment_link(payload)
        except LookupError as exc:
            return error_response(
                message=str(exc),
                code=status.HTTP_404_NOT_FOUND,
                errors={"provider": ["NIA not available"]},
            )
        except InsuranceProviderError as exc:
            return error_response(
                message="NIA generate payment link failed",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": str(exc)},
            )
        return success_response(message="NIA payment link generated successfully", data=data)


class NIAGetPaymentDetailsView(APIView):
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
            provider = _get_nia_provider()
            data = provider.get_payment_details(payload)
        except LookupError as exc:
            return error_response(
                message=str(exc),
                code=status.HTTP_404_NOT_FOUND,
                errors={"provider": ["NIA not available"]},
            )
        except InsuranceProviderError as exc:
            return error_response(
                message="NIA payment details fetch failed",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": str(exc)},
            )
        return success_response(message="NIA payment details fetched successfully", data=data)


class NIAGetQuoteView(APIView):
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
            provider = _get_nia_provider()
            normalized = provider.get_quote(payload)
        except LookupError as exc:
            return error_response(
                message=str(exc),
                code=status.HTTP_404_NOT_FOUND,
                errors={"provider": ["NIA not available"]},
            )
        except InsuranceProviderError as exc:
            return error_response(
                message="NIA quote failed",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": str(exc)},
            )
        return success_response(message="NIA quote fetched successfully", data=normalized.as_dict())


class NIAIssuePolicyView(APIView):
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
            provider = _get_nia_provider()
            data = provider.issue_policy(payload)
        except LookupError as exc:
            return error_response(
                message=str(exc),
                code=status.HTTP_404_NOT_FOUND,
                errors={"provider": ["NIA not available"]},
            )
        except InsuranceProviderError as exc:
            return error_response(
                message="NIA issue policy failed",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": str(exc)},
            )
        return success_response(message="NIA policy issue info fetched successfully", data=data)


class NIARenewPolicyView(APIView):
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
            provider = _get_nia_provider()
            data = provider.renew_policy(payload)
        except LookupError as exc:
            return error_response(
                message=str(exc),
                code=status.HTTP_404_NOT_FOUND,
                errors={"provider": ["NIA not available"]},
            )
        except InsuranceProviderError as exc:
            return error_response(
                message="NIA renew policy failed",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": str(exc)},
            )
        return success_response(message="NIA policy renewal quote fetched successfully", data=data)


class NIAFetchPolicyView(APIView):
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
            provider = _get_nia_provider()
            data = provider.fetch_policy(payload)
        except LookupError as exc:
            return error_response(
                message=str(exc),
                code=status.HTTP_404_NOT_FOUND,
                errors={"provider": ["NIA not available"]},
            )
        except InsuranceProviderError as exc:
            return error_response(
                message="NIA fetch policy failed",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": str(exc)},
            )
        return success_response(message="NIA policy fetched successfully", data=data)
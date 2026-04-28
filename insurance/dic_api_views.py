from __future__ import annotations

from typing import Any

import requests

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from api.responses import error_response, success_response
from insurance.models import InsuranceProvider
from insurance.providers import build_provider
from insurance.providers.dic_provider import DICProvider
from insurance.providers.exceptions import InsuranceProviderError


def _get_dic_provider() -> DICProvider:
    try:
        config = InsuranceProvider.objects.get(code__iexact="DIC", is_active=True)
    except InsuranceProvider.DoesNotExist as exc:
        raise LookupError("DIC provider is not configured or not active.") from exc
    provider = build_provider(config)
    if not isinstance(provider, DICProvider):
        raise TypeError("Configured DIC provider_class is not DICProvider.")
    return provider


class DICHealthCheckView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            provider = _get_dic_provider()
            data = provider.health_check()
        except LookupError as exc:
            return error_response(
                message=str(exc),
                code=status.HTTP_404_NOT_FOUND,
                errors={"provider": ["DIC not available"]},
            )
        except InsuranceProviderError as exc:
            return error_response(
                message="DIC health check failed",
                code=status.HTTP_503_SERVICE_UNAVAILABLE,
                errors={"detail": str(exc)},
            )
        return success_response(message="DIC health check completed", data=data)


class DICSupportedMasterdataView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            provider = _get_dic_provider()
            data = provider.get_supported_master_data()
        except LookupError as exc:
            return error_response(
                message=str(exc),
                code=status.HTTP_404_NOT_FOUND,
                errors={"provider": ["DIC not available"]},
            )
        return success_response(message="DIC masterdata fetched successfully", data=data)


class DICMasterdataView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, dataset: str):
        try:
            provider = _get_dic_provider()
            data = provider.get_master_data(dataset)
        except LookupError as exc:
            return error_response(
                message=str(exc),
                code=status.HTTP_404_NOT_FOUND,
                errors={"provider": ["DIC not available"]},
            )
        except KeyError:
            return error_response(
                message="Unsupported masterdata dataset",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"dataset": [dataset]},
            )
        return success_response(
            message="DIC masterdata fetched successfully",
            data={"dataset": dataset, "records": data},
        )


class DICAuthenticateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            provider = _get_dic_provider()
            token = provider.authenticate()
        except LookupError as exc:
            return error_response(
                message=str(exc),
                code=status.HTTP_404_NOT_FOUND,
                errors={"provider": ["DIC not available"]},
            )
        except InsuranceProviderError as exc:
            return error_response(
                message="DIC authentication failed",
                code=status.HTTP_401_UNAUTHORIZED,
                errors={"detail": str(exc)},
            )
        return success_response(message="DIC authenticated successfully", data={"token": token})


class DICGenerateQuoteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payload = request.data if isinstance(request.data, dict) else {}
        request_id = payload.get("request_id") if isinstance(payload, dict) else None
        try:
            provider = _get_dic_provider()
            data = provider.generate_quote(payload, request_id=request_id)
        except LookupError as exc:
            return error_response(
                message=str(exc),
                code=status.HTTP_404_NOT_FOUND,
                errors={"provider": ["DIC not available"]},
            )
        except InsuranceProviderError as exc:
            # DIC often returns useful JSON body even on 400/406. Base provider
            # currently only surfaces the HTTPError string, so we re-issue the
            # exact request once to capture DIC's response payload for clients.
            dic_error: dict[str, Any] | None = None
            dic_status: int | None = None
            try:
                provider = _get_dic_provider()
                config = provider.provider_config
                req_payload = provider._build_generate_quote_request(payload)
                token = provider.authenticate()
                url = f"{provider.get_base_url()}/{provider.GENERATE_QUOTE_ENDPOINT.lstrip('/')}"
                headers = {
                    "Accept": "application/json",
                    "Authorization": f"Bearer {token}" if token else "",
                    "X-REQUEST-ID": str(request_id or ""),
                }
                resp = requests.post(
                    url,
                    json=req_payload,
                    headers={k: v for k, v in headers.items() if v},
                    timeout=getattr(config, "timeout", None) or 30,
                )
                dic_status = resp.status_code
                try:
                    dic_error = resp.json()
                except Exception:
                    dic_error = {"raw": (resp.text or "").strip()}
            except Exception:
                dic_error = None
            return error_response(
                message="DIC generate quote failed",
                code=status.HTTP_400_BAD_REQUEST,
                errors={
                    "detail": str(exc),
                    "dic_status": dic_status,
                    "dic_response": dic_error,
                },
            )
        return success_response(message="DIC quote generated successfully", data=data)


class DICChooseSchemeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payload = request.data if isinstance(request.data, dict) else {}
        request_id = payload.get("request_id") or request.headers.get("X-REQUEST-ID")
        scheme_payload = payload.get("scheme") if isinstance(payload.get("scheme"), dict) else payload
        if not request_id:
            return error_response(
                message="Missing request_id",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"request_id": ["Provide request_id in body or X-REQUEST-ID header."]},
            )
        try:
            provider = _get_dic_provider()
            data = provider.choose_scheme(scheme_payload, request_id=str(request_id))
        except LookupError as exc:
            return error_response(
                message=str(exc),
                code=status.HTTP_404_NOT_FOUND,
                errors={"provider": ["DIC not available"]},
            )
        except InsuranceProviderError as exc:
            return error_response(
                message="DIC choose scheme failed",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": str(exc)},
            )
        return success_response(message="DIC scheme selected successfully", data=data)


class DICPaymentInfoView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        request_id = request.query_params.get("request_id") or request.headers.get("X-REQUEST-ID")
        tran_id = request.query_params.get("tran_id") or request.query_params.get("quotation_no")
        if not request_id:
            return error_response(
                message="Missing request_id",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"request_id": ["Provide request_id query param or X-REQUEST-ID header."]},
            )
        try:
            provider = _get_dic_provider()
            data = provider.get_payment_info(request_id=str(request_id), tran_id=tran_id)
        except LookupError as exc:
            return error_response(
                message=str(exc),
                code=status.HTTP_404_NOT_FOUND,
                errors={"provider": ["DIC not available"]},
            )
        except InsuranceProviderError as exc:
            return error_response(
                message="DIC payment info fetch failed",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": str(exc)},
            )
        return success_response(message="DIC payment info fetched successfully", data=data)


class DICGetQuoteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payload: dict[str, Any] = request.data if isinstance(request.data, dict) else {}
        try:
            provider = _get_dic_provider()
            normalized = provider.get_quote(payload)
        except LookupError as exc:
            return error_response(
                message=str(exc),
                code=status.HTTP_404_NOT_FOUND,
                errors={"provider": ["DIC not available"]},
            )
        except InsuranceProviderError as exc:
            return error_response(
                message="DIC quote failed",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": str(exc)},
            )
        return success_response(message="DIC quote fetched successfully", data=normalized.as_dict())


class DICIssuePolicyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payload: dict[str, Any] = request.data if isinstance(request.data, dict) else {}
        try:
            provider = _get_dic_provider()
            data = provider.issue_policy(payload)
        except LookupError as exc:
            return error_response(
                message=str(exc),
                code=status.HTTP_404_NOT_FOUND,
                errors={"provider": ["DIC not available"]},
            )
        except InsuranceProviderError as exc:
            return error_response(
                message="DIC issue policy failed",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": str(exc)},
            )
        return success_response(message="DIC policy issue info fetched successfully", data=data)


class DICFetchPolicyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payload: dict[str, Any] = request.data if isinstance(request.data, dict) else {}
        try:
            provider = _get_dic_provider()
            data = provider.fetch_policy(payload)
        except LookupError as exc:
            return error_response(
                message=str(exc),
                code=status.HTTP_404_NOT_FOUND,
                errors={"provider": ["DIC not available"]},
            )
        except InsuranceProviderError as exc:
            return error_response(
                message="DIC fetch policy failed",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": str(exc)},
            )
        return success_response(message="DIC policy fetched successfully", data=data)


class DICDownloadPolicyDocumentsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payload: dict[str, Any] = request.data if isinstance(request.data, dict) else {}
        try:
            provider = _get_dic_provider()
            data = provider.download_policy_documents(payload)
        except LookupError as exc:
            return error_response(
                message=str(exc),
                code=status.HTTP_404_NOT_FOUND,
                errors={"provider": ["DIC not available"]},
            )
        except InsuranceProviderError as exc:
            return error_response(
                message="DIC document download failed",
                code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": str(exc)},
            )
        return success_response(message="DIC policy documents fetched successfully", data=data)


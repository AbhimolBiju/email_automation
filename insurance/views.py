from rest_framework.decorators import api_view
from rest_framework import status
from deals.models import Deal
from leads.models import Lead
from .models import InsuranceInfo, InsuranceProvider
from .serializers import InsuranceInfoSerializer, InsuranceProviderSerializer
from rest_framework.exceptions import NotFound
from api.responses import success_response, error_response

from .services import get_best_quotes, health_check_provider

@api_view(['GET'])
def get_insurance_info(request, lead_id):
    try:
        lead = Lead.objects.get(id=lead_id)
    except Lead.DoesNotExist:
        raise NotFound("Lead not found")

    try:
        insurance_info = lead.insurance_info
    except InsuranceInfo.DoesNotExist:
        return success_response(
            message="Insurance info fetched successfully",
            data={},
            meta={"lead_id": str(lead.id)},
            status_code=status.HTTP_200_OK,
        )

    serializer = InsuranceInfoSerializer(insurance_info)
    return success_response(
        message="Insurance info fetched successfully",
        data=serializer.data,
        meta={"lead_id": str(lead.id)},
        status_code=status.HTTP_200_OK,
    )


@api_view(["GET"])
def list_insurance_providers(request):
    providers = InsuranceProvider.objects.all().order_by("priority", "name")
    serializer = InsuranceProviderSerializer(providers, many=True)
    return success_response(
        message="Insurance providers fetched successfully",
        data=serializer.data,
        status_code=status.HTTP_200_OK,
    )


@api_view(["POST"])
def provider_health_check(request, provider_id):
    try:
        provider = InsuranceProvider.objects.get(id=provider_id)
    except InsuranceProvider.DoesNotExist:
        raise NotFound("Insurance provider not found")

    try:
        result = health_check_provider(provider)
    except Exception as exc:
        return error_response(
            message="Provider health check failed",
            code=status.HTTP_503_SERVICE_UNAVAILABLE,
            errors={"provider": provider.code, "detail": str(exc)},
        )

    return success_response(
        message="Provider health check completed",
        data={
            "provider": provider.code,
            "result": result,
        },
        status_code=status.HTTP_200_OK,
    )


@api_view(["POST"])
def get_deal_quotes(request, deal_id):
    try:
        result = get_best_quotes(deal_id)
    except Deal.DoesNotExist:
        raise NotFound("Deal not found")
    except Exception as exc:
        return error_response(
            message="Failed to fetch quotes",
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            errors={"detail": str(exc)},
        )

    return success_response(
        message="Quotes fetched successfully",
        data=result,
        status_code=status.HTTP_200_OK,
    )

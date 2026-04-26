from insurance.models import InsuranceProvider
from insurance.providers import build_provider


def get_active_provider_configs():
    return InsuranceProvider.objects.filter(is_active=True).order_by("priority", "name")


def get_active_provider_instances():
    return [(provider, build_provider(provider)) for provider in get_active_provider_configs()]


def health_check_provider(provider: InsuranceProvider) -> dict:
    return build_provider(provider).health_check()

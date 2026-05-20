from importlib import import_module

from insurance.models import InsuranceProvider

from .exceptions import ProviderConfigurationError
from .registry import PROVIDER_CLASS_REGISTRY


def resolve_provider_class(provider_class: str):
    module_path = PROVIDER_CLASS_REGISTRY.get(provider_class)
    if module_path is None and provider_class in PROVIDER_CLASS_REGISTRY.values():
        module_path = provider_class
    if module_path is None:
        raise ProviderConfigurationError(
            f"Unsupported provider class '{provider_class}'."
        )

    import_path, class_name = module_path.rsplit(".", 1)
    module = import_module(import_path)
    provider_cls = getattr(module, class_name, None)
    if provider_cls is None:
        raise ProviderConfigurationError(
            f"Provider class '{module_path}' could not be imported."
        )
    return provider_cls


def build_provider(provider_config: InsuranceProvider):
    provider_cls = resolve_provider_class(provider_config.provider_class)
    return provider_cls(provider_config)

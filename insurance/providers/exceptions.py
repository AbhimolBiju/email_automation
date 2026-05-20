class InsuranceProviderError(Exception):
    pass


class ProviderConfigurationError(InsuranceProviderError):
    pass


class ProviderAuthenticationError(InsuranceProviderError):
    pass


class ProviderRequestError(InsuranceProviderError):
    pass


class ProviderCircuitOpenError(InsuranceProviderError):
    pass

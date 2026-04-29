from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class NormalizedQuote:
    provider: str
    premium: Decimal
    vat: Decimal
    total: Decimal
    currency: str
    plan_name: str
    response_time_ms: int
    status: str = "SUCCESS"
    benefits: dict[str, Any] = field(default_factory=dict)
    optional_covers: dict[str, Any] = field(default_factory=dict)
    vehicle_details: dict[str, Any] = field(default_factory=dict)
    coverage_amount: str | None = None
    deductible: str | None = None
    coverage_score: float = 0
    raw_response: dict[str, Any] = field(default_factory=dict)

    def as_dict(self, *, include_raw_response: bool = False) -> dict[str, Any]:
        data = {
            "provider": self.provider,
            "premium": float(self.premium),
            "vat": float(self.vat),
            "total": float(self.total),
            "currency": self.currency,
            "plan_name": self.plan_name,
            "response_time_ms": self.response_time_ms,
            "status": self.status,
            "benefits": self.benefits,
            "optional_covers": self.optional_covers,
            "vehicle_details": self.vehicle_details,
            "coverage_amount": self.coverage_amount,
            "deductible": self.deductible,
            "coverage_score": self.coverage_score,
        }
        if include_raw_response:
            data["raw_response"] = self.raw_response
        return data

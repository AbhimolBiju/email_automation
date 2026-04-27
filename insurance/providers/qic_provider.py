from __future__ import annotations

import base64
import time
import uuid
from decimal import Decimal
from typing import Any

from .base import BaseInsuranceProvider
from .exceptions import ProviderAuthenticationError, ProviderRequestError
from .qic_masterdata import (
    load_body_type_records,
    load_cylinder_records,
    load_nationality_records,
    load_regn_location_records,
    lookup_bayanaty_make_model_ids,
    lookup_body_type_code,
    lookup_cylinder_code,
    lookup_make_model_codes,
    lookup_nationality_code,
    lookup_regn_location_code,
)


class QICProvider(BaseInsuranceProvider):
    TARIFF_ENDPOINT = "/qicservices/aggregator/motor/tariff"
    NET_PREMIUM_ENDPOINT = "/qicservices/aggregator/motor/netPremium"
    SEND_PAY_LINK_ENDPOINT = "/qicservices/aggregator/sendPayLink"
    QUOTE_SCHEDULE_ENDPOINT = "/qicservices/aggregator/getQuoteSchedule"
    POLICY_REPORT_ENDPOINT = "/qicservices/aggregator/getPolicyReport"
    POLICY_LOOKUP_ENDPOINT = "/qicservices/aggregator/getLeadPolList"

    BAYANATY_VEHICLE_DETAILS_ENDPOINT = "/qicservices/aggregator/bayanaty/vehicleDetails"
    BAYANATY_IMPORTED_DETAILS_ENDPOINT = "/qicservices/aggregator/bayanaty/vehicleImpDetails"
    BAYANATY_SPEC_DETAILS_ENDPOINT = "/qicservices/aggregator/bayanaty/vehicleSpecDetails"
    BAYANATY_VALUATION_ENDPOINT = "/qicservices/aggregator/bayanaty/vehicleValuation"
    BAYANATY_BODY_TYPE_ENDPOINT = "/qicservices/aggregator/bayanaty/bodyType"
    BAYANATY_ENGINE_CAPACITIES_ENDPOINT = "/qicservices/aggregator/bayanaty/engineCapacities"
    BAYANATY_TRIMS_ENDPOINT = "/qicservices/aggregator/bayanaty/trims"

    def _company_code(self) -> str:
        return str(self.get_extra_config().get("company_code", "002"))

    def get_base_url(self) -> str:
        base_url = super().get_base_url()
        if "www.devapi.anoudapps.com" in base_url and self.get_extra_config().get(
            "prefer_non_www_host",
            True,
        ):
            return base_url.replace("://www.devapi.anoudapps.com", "://devapi.anoudapps.com")
        return base_url

    def _basic_auth_value(self, username: str, password: str) -> str:
        return base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")

    def authenticate(self) -> str | None:
        username = self.resolve_config_value("username", "")
        password = self.resolve_config_value("password", "")
        if not username or not password:
            raise ProviderAuthenticationError(
                "QIC requires username and password for basic authentication."
            )
        return self._basic_auth_value(username, password)

    def get_auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Basic {self.authenticate()}",
            "company": self._company_code(),
        }

    def _bayanaty_auth_headers(self) -> dict[str, str]:
        username = str(self.get_extra_config().get("bayanaty_username") or self.resolve_config_value("username", ""))
        password = str(self.get_extra_config().get("bayanaty_password") or self.resolve_config_value("password", ""))
        if not username or not password:
            raise ProviderAuthenticationError("QIC Bayanaty integration requires username and password.")
        return {
            "Authorization": f"Basic {self._basic_auth_value(username, password)}",
            "company": self._company_code(),
        }

    def _request_id(self, provided: str | None = None) -> str:
        return provided or str(uuid.uuid4())

    def _with_company(self, path: str) -> str:
        separator = "&" if "?" in path else "?"
        if "company=" in path:
            return path
        return f"{path}{separator}company={self._company_code()}"

    def _ensure_success(self, payload: dict[str, Any]) -> dict[str, Any]:
        resp_code = str(payload.get("respCode", "")).strip()
        if resp_code and resp_code not in {"0", "200", "SUCCESS"}:
            raise ProviderRequestError(str(payload.get("errMessage") or f"QIC request failed with respCode {resp_code}."))
        return payload

    def _build_tariff_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        customer = payload.get("customer") if isinstance(payload.get("customer"), dict) else payload
        vehicle = payload.get("vehicle") if isinstance(payload.get("vehicle"), dict) else payload
        make_code, model_code = lookup_make_model_codes(
            payload.get("make_id") or vehicle.get("make_id"),
            payload.get("model_id") or vehicle.get("model_id"),
        )
        return {
            "insuredName": str(customer.get("name") or payload.get("insured_name") or "Insured"),
            "policyFromDate": str(payload.get("policy_from_date") or ""),
            "makeCode": make_code,
            "modelCode": model_code,
            "modelYear": str(vehicle.get("model_year") or payload.get("model_year") or ""),
            "sumInsured": float(payload.get("sum_insured") or vehicle.get("sum_insured") or 0),
            "vehicleType": lookup_body_type_code(payload.get("body_type_id") or vehicle.get("body_type_id")),
            "vehicleUsage": str(payload.get("vehicle_usage") or vehicle.get("vehicle_usage") or "1001"),
            "noOfCylinder": lookup_cylinder_code(payload.get("no_of_cylinder") or vehicle.get("engine_capacity_id") or "1004"),
            "nationality": lookup_nationality_code(payload.get("nationality") or customer.get("nationality")),
            "seatingCapacity": str(payload.get("seating_capacity") or vehicle.get("seating_capacity") or "5"),
            "regYear": str(payload.get("reg_year") or vehicle.get("registration_year") or vehicle.get("model_year") or ""),
            "gccSpec": "1" if payload.get("is_gcc_spec") or vehicle.get("is_gcc_spec") else "0",
            "previousInsuranceValid": "1" if payload.get("previous_insurance_valid") else "0",
            "totalLoss": "1" if payload.get("total_loss") else "0",
            "driverDOB": str(payload.get("date_of_birth") or customer.get("date_of_birth") or ""),
            "insuredAge": int(payload.get("insured_age") or customer.get("insured_age") or 0),
            "noClaimYear": str(payload.get("ncd_years") or vehicle.get("ncd_years") or 0),
            "selfDeclarationYear": int(payload.get("self_declaration_year") or 0),
            "chassisNo": str(payload.get("chassis_number") or vehicle.get("chassis_number") or ""),
            "driverExp": int(payload.get("driver_experience") or 0),
            "admeId": int(self.get_extra_config().get("adme_id", payload.get("adme_id") or 401369)),
            "civilId": str(payload.get("civil_id") or customer.get("emirates_id") or ""),
            "firstRegDate": str(payload.get("reg_dt") or vehicle.get("registration_date") or ""),
            "mobileNo": str(payload.get("mobile_number") or customer.get("mobile_number") or ""),
            "emailId": str(payload.get("email_address") or customer.get("email") or ""),
            "engineNo": str(payload.get("engine_no") or vehicle.get("engine_no") or ""),
            "registrationNo": str(payload.get("reg_number") or vehicle.get("registration_number") or ""),
            "tcfNo": str(payload.get("tcf_number") or vehicle.get("tcf_number") or ""),
            "colorCode": str(payload.get("color_code") or vehicle.get("color_code") or ""),
            "financeYn": "1" if payload.get("finance_yn") else "0",
            "regnLocation": lookup_regn_location_code(payload.get("plate_source") or vehicle.get("plate_source")),
        }

    def get_tariff(self, payload: dict[str, Any]) -> dict[str, Any]:
        mock_payload = self.get_extra_config().get("mock_tariff_response")
        if isinstance(mock_payload, dict):
            return mock_payload
        response = self._request(
            method="POST",
            path=self._with_company(self.get_extra_config().get("tariff_endpoint", self.TARIFF_ENDPOINT)),
            json_payload=self._build_tariff_request(payload),
        )
        return self._ensure_success(response)

    def get_net_premium(self, payload: dict[str, Any]) -> dict[str, Any]:
        mock_payload = self.get_extra_config().get("mock_net_premium_response")
        if isinstance(mock_payload, dict):
            return mock_payload
        response = self._request(
            method="POST",
            path=self._with_company(self.get_extra_config().get("net_premium_endpoint", self.NET_PREMIUM_ENDPOINT)),
            json_payload=payload,
        )
        return self._ensure_success(response)

    def send_payment_link(self, payload: dict[str, Any]) -> dict[str, Any]:
        mock_payload = self.get_extra_config().get("mock_send_pay_link_response")
        if isinstance(mock_payload, dict):
            return mock_payload
        response = self._request(
            method="POST",
            path=self._with_company(self.get_extra_config().get("send_pay_link_endpoint", self.SEND_PAY_LINK_ENDPOINT)),
            json_payload=payload,
        )
        return self._ensure_success(response)

    def download_quote_document(self, *, quote_no: str, doc_type: str = "Quotation") -> dict[str, Any]:
        response = self._request(
            method="GET",
            path=self._with_company(
                f"{self.get_extra_config().get('quote_schedule_endpoint', self.QUOTE_SCHEDULE_ENDPOINT)}?quoteNo={quote_no}&docType={doc_type}"
            ),
            authenticated=True,
        )
        return response

    def download_documents(self, payload: dict[str, Any]) -> dict[str, Any]:
        policy_no = str(payload.get("policy_no") or "")
        doc_type = str(payload.get("doc_type") or "Schedule")
        response = self._request(
            method="GET",
            path=self._with_company(
                f"{self.get_extra_config().get('policy_report_endpoint', self.POLICY_REPORT_ENDPOINT)}?policyNo={policy_no}&docType={doc_type}"
            ),
            authenticated=True,
        )
        return response

    def fetch_policy(self, payload: dict[str, Any]) -> dict[str, Any]:
        mock_payload = self.get_extra_config().get("mock_policy_lookup_response")
        if isinstance(mock_payload, dict):
            return mock_payload
        response = self._request(
            method="POST",
            path=self._with_company(self.get_extra_config().get("policy_lookup_endpoint", self.POLICY_LOOKUP_ENDPOINT)),
            json_payload=payload,
        )
        return self._ensure_success(response)

    def get_quote(self, payload: dict[str, Any]):
        started = time.perf_counter()
        mock_payload = self.get_extra_config().get("mock_quote_response")
        if isinstance(mock_payload, dict):
            return self.build_quote_from_mapping(
                mock_payload,
                response_time_ms=int((time.perf_counter() - started) * 1000),
            )

        tariff = self.get_tariff(payload)
        quote_no = str(tariff.get("quoteNo") or tariff.get("quotationNo") or "")
        products = tariff.get("products") or tariff.get("schemes") or tariff.get("data") or []
        if not quote_no or not isinstance(products, list) or not products:
            raise ProviderRequestError("QIC tariff response did not include quote number and schemes.")

        normalized_quotes: list[dict[str, Any]] = []
        for product in products:
            schemes = product.get("schemes") or []
            for scheme in schemes:
                premium_payload = {
                    "quoteNo": quote_no,
                    "schemes": [
                        {
                            "schemeCode": str(scheme.get("schemeCode") or ""),
                            "productCode": str(product.get("productCode") or product.get("prodCode") or ""),
                        }
                    ],
                }
                premium_data = self.get_net_premium(premium_payload)
                normalized_quotes.append(
                    {
                        "product": product,
                        "scheme": scheme,
                        "premium": premium_data,
                    }
                )

        if not normalized_quotes:
            raise ProviderRequestError("QIC did not return any net premium options.")

        best = min(
            normalized_quotes,
            key=lambda item: Decimal(str(item["premium"].get("netPremium") or 0)),
        )
        premium = best["premium"]
        return self.build_quote_from_mapping(
            {
                "premium": premium.get("netPremium", 0),
                "vat": premium.get("taxAmount", 0),
                "total": premium.get("netPremium", 0),
                "currency": "AED",
                "plan_name": best["scheme"].get("schemeDescription")
                or best["scheme"].get("schemeCode")
                or "QIC Plan",
                "quote_no": quote_no,
                "tariff": tariff,
                "selected_premium": premium,
            },
            response_time_ms=int((time.perf_counter() - started) * 1000),
        )

    def issue_policy(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.send_payment_link(payload)

    def renew_policy(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.get_tariff(payload)

    def bayanaty_vehicle_details(self, vin: str) -> dict[str, Any]:
        return self._request(
            method="POST",
            path=self._with_company(self.BAYANATY_VEHICLE_DETAILS_ENDPOINT),
            json_payload={"Vin": vin},
            extra_headers=self._bayanaty_auth_headers(),
        )

    def bayanaty_imported_details(self, vin: str) -> dict[str, Any]:
        return self._request(
            method="POST",
            path=self._with_company(self.BAYANATY_IMPORTED_DETAILS_ENDPOINT),
            json_payload={"Vin": vin},
            extra_headers=self._bayanaty_auth_headers(),
        )

    def bayanaty_vehicle_spec(self, vin: str) -> dict[str, Any]:
        return self._request(
            method="POST",
            path=self._with_company(self.BAYANATY_SPEC_DETAILS_ENDPOINT),
            json_payload={"Vin": vin},
            extra_headers=self._bayanaty_auth_headers(),
        )

    def bayanaty_vehicle_valuation(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            method="POST",
            path=self._with_company(self.BAYANATY_VALUATION_ENDPOINT),
            json_payload=payload,
            extra_headers=self._bayanaty_auth_headers(),
        )

    def bayanaty_body_type(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            method="POST",
            path=self._with_company(self.BAYANATY_BODY_TYPE_ENDPOINT),
            json_payload=payload,
            extra_headers=self._bayanaty_auth_headers(),
        )

    def bayanaty_engine_capacities(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            method="POST",
            path=self._with_company(self.BAYANATY_ENGINE_CAPACITIES_ENDPOINT),
            json_payload=payload,
            extra_headers=self._bayanaty_auth_headers(),
        )

    def bayanaty_trims(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            method="POST",
            path=self._with_company(self.BAYANATY_TRIMS_ENDPOINT),
            json_payload=payload,
            extra_headers=self._bayanaty_auth_headers(),
        )

    def health_check(self) -> dict[str, Any]:
        mock_payload = self.get_extra_config().get("mock_health_check")
        if isinstance(mock_payload, dict):
            return mock_payload
        self.authenticate()
        return {
            "status": "ok",
            "company_code": self._company_code(),
            "masterdata_sets": {
                "body_types": len(load_body_type_records()),
                "cylinders": len(load_cylinder_records()),
                "nationalities": len(load_nationality_records()),
                "registration_locations": len(load_regn_location_records()),
            },
        }

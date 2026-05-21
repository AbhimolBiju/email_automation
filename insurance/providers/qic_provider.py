# from __future__ import annotations

# import base64
# from datetime import date, datetime
# import re
# import time
# import uuid
# from decimal import Decimal
# from typing import Any

# from .base import BaseInsuranceProvider
# from .exceptions import ProviderAuthenticationError, ProviderRequestError
# from .qic_masterdata import (
#     load_body_type_records,
#     load_cylinder_records,
#     load_nationality_records,
#     load_regn_location_records,
#     lookup_bayanaty_make_model_ids,
#     lookup_body_type_code,
#     lookup_cylinder_code,
#     lookup_make_model_codes,
#     lookup_nationality_code,
#     lookup_regn_location_code,
# )


# class QICProvider(BaseInsuranceProvider):
#     TARIFF_ENDPOINT = "/qicservices/aggregator/motor/tariff"
#     NET_PREMIUM_ENDPOINT = "/qicservices/aggregator/motor/netPremium"
#     SEND_PAY_LINK_ENDPOINT = "/qicservices/aggregator/sendPayLink"
#     QUOTE_SCHEDULE_ENDPOINT = "/qicservices/aggregator/getQuoteSchedule"
#     POLICY_REPORT_ENDPOINT = "/qicservices/aggregator/getPolicyReport"
#     POLICY_LOOKUP_ENDPOINT = "/qicservices/aggregator/getLeadPolList"

#     BAYANATY_VEHICLE_DETAILS_ENDPOINT = "/qicservices/aggregator/bayanaty/vehicleDetails"
#     BAYANATY_IMPORTED_DETAILS_ENDPOINT = "/qicservices/aggregator/bayanaty/vehicleImpDetails"
#     BAYANATY_SPEC_DETAILS_ENDPOINT = "/qicservices/aggregator/bayanaty/vehicleSpecDetails"
#     BAYANATY_VALUATION_ENDPOINT = "/qicservices/aggregator/bayanaty/vehicleValuation"
#     BAYANATY_BODY_TYPE_ENDPOINT = "/qicservices/aggregator/bayanaty/bodyType"
#     BAYANATY_ENGINE_CAPACITIES_ENDPOINT = "/qicservices/aggregator/bayanaty/engineCapacities"
#     BAYANATY_TRIMS_ENDPOINT = "/qicservices/aggregator/bayanaty/trims"

#     def _company_code(self) -> str:
#         return str(self.get_extra_config().get("company_code", "002"))

#     def get_base_url(self) -> str:
#         base_url = super().get_base_url()
#         if "www.devapi.anoudapps.com" in base_url and self.get_extra_config().get(
#             "prefer_non_www_host",
#             True,
#         ):
#             return base_url.replace("://www.devapi.anoudapps.com", "://devapi.anoudapps.com")
#         return base_url

#     def _basic_auth_value(self, username: str, password: str) -> str:
#         return base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")

#     def authenticate(self) -> str | None:
#         username = self.resolve_config_value("username", "")
#         password = self.resolve_config_value("password", "")
#         if not username or not password:
#             raise ProviderAuthenticationError(
#                 "QIC requires username and password for basic authentication."
#             )
#         return self._basic_auth_value(username, password)

#     def get_auth_headers(self) -> dict[str, str]:
#         return {
#             "Authorization": f"Basic {self.authenticate()}",
#             "company": self._company_code(),
#         }
    
#     def _format_date(self, value: Any) -> str:
#         text = str(value).strip() if value not in (None, "") else ""
#         if not text:
#             return ""
#         for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"):
#             try:
#                 return datetime.strptime(text, fmt).strftime("%d/%m/%Y")
#             except ValueError:
#                 continue
#         raise ValueError(f"Invalid date format: {value}")



#     def _bayanaty_auth_headers(self) -> dict[str, str]:
#         username = str(self.get_extra_config().get("bayanaty_username") or self.resolve_config_value("username", ""))
#         password = str(self.get_extra_config().get("bayanaty_password") or self.resolve_config_value("password", ""))
#         if not username or not password:
#             raise ProviderAuthenticationError("QIC Bayanaty integration requires username and password.")
#         return {
#             "Authorization": f"Basic {self._basic_auth_value(username, password)}",
#             "company": self._company_code(),
#         }

#     def _request_id(self, provided: str | None = None) -> str:
#         return provided or str(uuid.uuid4())

#     def _with_company(self, path: str) -> str:
#         separator = "&" if "?" in path else "?"
#         if "company=" in path:
#             return path
#         return f"{path}{separator}company={self._company_code()}"

#     def _ensure_success(self, payload: dict[str, Any]) -> dict[str, Any]:
#         resp_code = str(payload.get("respCode", "")).strip()
#         if resp_code and resp_code not in {"0", "200", "SUCCESS"}:
#             raise ProviderRequestError(str(payload.get("errMessage") or f"QIC request failed with respCode {resp_code}."))
#         return payload

#     def _format_first_registration_date(self, value: Any) -> str:
#         """
#         QIC requires `firstRegDate` as `YYYY-MM-DD`, not future-dated.
#         Accepts: date/datetime objects, ISO strings, or `YYYY`.
#         """
#         if value is None:
#             return ""
#         if isinstance(value, datetime):
#             parsed = value.date()
#         elif isinstance(value, date):
#             parsed = value
#         else:
#             text = str(value).strip()
#             if not text:
#                 return ""
#             # Common ISO date formats: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS...
#             try:
#                 parsed = datetime.fromisoformat(text.replace("Z", "+00:00")).date()
#             except Exception:
#                 # Fallback: `YYYY` only
#                 if re.fullmatch(r"\d{4}", text):
#                     parsed = date(int(text), 1, 1)
#                 else:
#                     return ""

#         if parsed > date.today():
#             return ""
#         return parsed.isoformat()

#     def _resolve_first_registration_date(self, payload: dict[str, Any], vehicle: dict[str, Any]) -> str:
#         # Priority requested by user: vehicle.first_registration_date OR registration_date OR manufacture_year/year.
#         candidates = [
#             vehicle.get("first_registration_date"),
#             payload.get("first_registration_date"),
#             vehicle.get("registration_date"),
#             payload.get("reg_dt"),
#             vehicle.get("registration_year"),
#             vehicle.get("manufacture_year"),
#             vehicle.get("year"),
#             vehicle.get("model_year"),
#             payload.get("model_year"),
#         ]
#         for candidate in candidates:
#             formatted = self._format_first_registration_date(candidate)
#             if formatted:
#                 return formatted

#         # Final fallback: `{vehicle.year}-01-01`
#         year = vehicle.get("year") or vehicle.get("model_year") or payload.get("model_year")
#         try:
#             year_int = int(str(year).strip())
#         except Exception:
#             year_int = 0
#         if 1900 <= year_int <= date.today().year:
#             return date(year_int, 1, 1).isoformat()
#         return ""

#     def _build_tariff_request(self, payload: dict[str, Any]) -> dict[str, Any]:
#         customer = payload.get("customer") if isinstance(payload.get("customer"), dict) else payload
#         vehicle = payload.get("vehicle") if isinstance(payload.get("vehicle"), dict) else payload
#         make_code, model_code = lookup_make_model_codes(
#             payload.get("make_id") or vehicle.get("make_id"),
#             payload.get("model_id") or vehicle.get("model_id"),
#         )
#         sum_insured = float(payload.get("sum_insured") or vehicle.get("sum_insured") or 0)
#         if sum_insured <= 0:
#             default_sum_insured = self.get_extra_config().get("default_sum_insured")
#             if default_sum_insured not in (None, "", 0, "0"):
#                 sum_insured = float(default_sum_insured)
#             else:
#                 raise ProviderRequestError(
#                     "QIC requires sum_insured (vehicle valuation) in the quote payload."
#                 )
#         return {
#             "insuredName": str(customer.get("name") or payload.get("insured_name") or "Insured"),
#             "policyFromDate": self._format_date(payload.get("policy_from_date")),
#             "makeCode": make_code,
#             "modelCode": model_code,
#             "modelYear": str(vehicle.get("model_year") or payload.get("model_year") or ""),
#             "sumInsured": sum_insured,
#             "vehicleType": lookup_body_type_code(payload.get("body_type_id") or vehicle.get("body_type_id")),
#             "vehicleUsage": str(payload.get("vehicle_usage") or vehicle.get("vehicle_usage") or "1001"),
#             "noOfCylinder": lookup_cylinder_code(payload.get("no_of_cylinder") or vehicle.get("engine_capacity_id") or "1004"),
#             "nationality": lookup_nationality_code(payload.get("nationality") or customer.get("nationality")),
#             "seatingCapacity": str(payload.get("seating_capacity") or vehicle.get("seating_capacity") or "5"),
#             "regYear": str(payload.get("reg_year") or vehicle.get("registration_year") or vehicle.get("model_year") or ""),
#             "gccSpec": "1" if payload.get("is_gcc_spec") or vehicle.get("is_gcc_spec") else "0",
#             "previousInsuranceValid": "1" if payload.get("previous_insurance_valid") else "0",
#             "totalLoss": "1" if payload.get("total_loss") else "0",
#            "driverDOB": self._format_date(payload.get("date_of_birth") or customer.get("date_of_birth")),
#             "insuredAge": int(payload.get("insured_age") or customer.get("insured_age") or 0),
#             "noClaimYear": str(payload.get("ncd_years") or vehicle.get("ncd_years") or 0),
#             "selfDeclarationYear": int(payload.get("self_declaration_year") or 0),
#             "chassisNo": str(payload.get("chassis_number") or vehicle.get("chassis_number") or ""),
#             "driverExp": int(payload.get("driver_experience") or 0),
#             "admeId": int(self.get_extra_config().get("adme_id", payload.get("adme_id") or 401369)),
#             "civilId": str(payload.get("civil_id") or customer.get("emirates_id") or ""),

#             "firstRegDate": self._format_date(payload.get("reg_dt") or vehicle.get("registration_date")),

#             # "firstRegDate": self._resolve_first_registration_date(payload, vehicle),

#             "mobileNo": str(payload.get("mobile_number") or customer.get("mobile_number") or ""),
#             "emailId": str(payload.get("email_address") or customer.get("email") or ""),
#             "engineNo": str(payload.get("engine_no") or vehicle.get("engine_no") or ""),
#             "registrationNo": str(payload.get("reg_number") or vehicle.get("registration_number") or ""),
#             "tcfNo": str(payload.get("tcf_number") or vehicle.get("tcf_number") or ""),
#             "colorCode": str(payload.get("color_code") or vehicle.get("color_code") or ""),
#             "financeYn": "1" if payload.get("finance_yn") else "0",
#             "regnLocation": lookup_regn_location_code(payload.get("plate_source") or vehicle.get("plate_source")),
#         }

#     def get_tariff(self, payload: dict[str, Any]) -> dict[str, Any]:
#         mock_payload = self.get_extra_config().get("mock_tariff_response")
#         if isinstance(mock_payload, dict):
#             return mock_payload
#         tariff_payload = self._build_tariff_request(payload)
#         if not str(tariff_payload.get("firstRegDate") or "").strip():
#             raise ProviderRequestError(
#                 "QIC requires first_registration_date (firstRegDate) in YYYY-MM-DD format (not future-dated)."
#             )
#         print("QIC payload:", tariff_payload)
#         response = self._request(
#             method="POST",
#             path=self._with_company(self.get_extra_config().get("tariff_endpoint", self.TARIFF_ENDPOINT)),
#             json_payload=tariff_payload,
#         )
#         return self._ensure_success(response)

#     def get_net_premium(self, payload: dict[str, Any]) -> dict[str, Any]:
#         mock_payload = self.get_extra_config().get("mock_net_premium_response")
#         if isinstance(mock_payload, dict):
#             return mock_payload
#         response = self._request(
#             method="POST",
#             path=self._with_company(self.get_extra_config().get("net_premium_endpoint", self.NET_PREMIUM_ENDPOINT)),
#             json_payload=payload,
#         )
#         return self._ensure_success(response)

#     def send_payment_link(self, payload: dict[str, Any]) -> dict[str, Any]:
#         mock_payload = self.get_extra_config().get("mock_send_pay_link_response")
#         if isinstance(mock_payload, dict):
#             return mock_payload
#         response = self._request(
#             method="POST",
#             path=self._with_company(self.get_extra_config().get("send_pay_link_endpoint", self.SEND_PAY_LINK_ENDPOINT)),
#             json_payload=payload,
#         )
#         return self._ensure_success(response)

#     def download_quote_document(self, *, quote_no: str, doc_type: str = "Quotation") -> dict[str, Any]:
#         response = self._request(
#             method="GET",
#             path=self._with_company(
#                 f"{self.get_extra_config().get('quote_schedule_endpoint', self.QUOTE_SCHEDULE_ENDPOINT)}?quoteNo={quote_no}&docType={doc_type}"
#             ),
#             authenticated=True,
#         )
#         return response

#     def download_documents(self, payload: dict[str, Any]) -> dict[str, Any]:
#         policy_no = str(payload.get("policy_no") or "")
#         doc_type = str(payload.get("doc_type") or "Schedule")
#         response = self._request(
#             method="GET",
#             path=self._with_company(
#                 f"{self.get_extra_config().get('policy_report_endpoint', self.POLICY_REPORT_ENDPOINT)}?policyNo={policy_no}&docType={doc_type}"
#             ),
#             authenticated=True,
#         )
#         return response

#     def fetch_policy(self, payload: dict[str, Any]) -> dict[str, Any]:
#         mock_payload = self.get_extra_config().get("mock_policy_lookup_response")
#         if isinstance(mock_payload, dict):
#             return mock_payload
#         response = self._request(
#             method="POST",
#             path=self._with_company(self.get_extra_config().get("policy_lookup_endpoint", self.POLICY_LOOKUP_ENDPOINT)),
#             json_payload=payload,
#         )
#         return self._ensure_success(response)

#     def get_quote(self, payload: dict[str, Any]):
#         started = time.perf_counter()
#         mock_payload = self.get_extra_config().get("mock_quote_response")
#         if isinstance(mock_payload, dict):
#             return self.build_quote_from_mapping(
#                 mock_payload,
#                 response_time_ms=int((time.perf_counter() - started) * 1000),
#             )

#         tariff = self.get_tariff(payload)
#         quote_no = str(tariff.get("quoteNo") or tariff.get("quotationNo") or "")
#         products = tariff.get("products") or tariff.get("schemes") or tariff.get("data") or []
#         if not quote_no or not isinstance(products, list) or not products:
#             raise ProviderRequestError("QIC tariff response did not include quote number and schemes.")

#         normalized_quotes: list[dict[str, Any]] = []
#         for product in products:
#             schemes = product.get("schemes") or []
#             for scheme in schemes:
#                 premium_payload = {
#                     "quoteNo": quote_no,
#                     "schemes": [
#                         {
#                             "schemeCode": str(scheme.get("schemeCode") or ""),
#                             "productCode": str(product.get("productCode") or product.get("prodCode") or ""),
#                         }
#                     ],
#                 }
#                 premium_data = self.get_net_premium(premium_payload)
#                 normalized_quotes.append(
#                     {
#                         "product": product,
#                         "scheme": scheme,
#                         "premium": premium_data,
#                     }
#                 )

#         if not normalized_quotes:
#             raise ProviderRequestError("QIC did not return any net premium options.")

#         best = min(
#             normalized_quotes,
#             key=lambda item: Decimal(str(item["premium"].get("netPremium") or 0)),
#         )
#         premium = best["premium"]
#         return self.build_quote_from_mapping(
#             {
#                 "premium": premium.get("netPremium", 0),
#                 "vat": premium.get("taxAmount", 0),
#                 "total": premium.get("netPremium", 0),
#                 "currency": "AED",
#                 "plan_name": best["scheme"].get("schemeDescription")
#                 or best["scheme"].get("schemeCode")
#                 or "QIC Plan",
#                 "quote_no": quote_no,
#                 "tariff": tariff,
#                 "selected_premium": premium,
#             },
#             response_time_ms=int((time.perf_counter() - started) * 1000),
#         )

#     def issue_policy(self, payload: dict[str, Any]) -> dict[str, Any]:
#         return self.send_payment_link(payload)

#     def renew_policy(self, payload: dict[str, Any]) -> dict[str, Any]:
#         return self.get_tariff(payload)

#     def bayanaty_vehicle_details(self, vin: str) -> dict[str, Any]:
#         return self._request(
#             method="POST",
#             path=self._with_company(self.BAYANATY_VEHICLE_DETAILS_ENDPOINT),
#             json_payload={"Vin": vin},
#             extra_headers=self._bayanaty_auth_headers(),
#         )

#     def bayanaty_imported_details(self, vin: str) -> dict[str, Any]:
#         return self._request(
#             method="POST",
#             path=self._with_company(self.BAYANATY_IMPORTED_DETAILS_ENDPOINT),
#             json_payload={"Vin": vin},
#             extra_headers=self._bayanaty_auth_headers(),
#         )

#     def bayanaty_vehicle_spec(self, vin: str) -> dict[str, Any]:
#         return self._request(
#             method="POST",
#             path=self._with_company(self.BAYANATY_SPEC_DETAILS_ENDPOINT),
#             json_payload={"Vin": vin},
#             extra_headers=self._bayanaty_auth_headers(),
#         )

#     def bayanaty_vehicle_valuation(self, payload: dict[str, Any]) -> dict[str, Any]:
#         return self._request(
#             method="POST",
#             path=self._with_company(self.BAYANATY_VALUATION_ENDPOINT),
#             json_payload=payload,
#             extra_headers=self._bayanaty_auth_headers(),
#         )

#     def bayanaty_body_type(self, payload: dict[str, Any]) -> dict[str, Any]:
#         return self._request(
#             method="POST",
#             path=self._with_company(self.BAYANATY_BODY_TYPE_ENDPOINT),
#             json_payload=payload,
#             extra_headers=self._bayanaty_auth_headers(),
#         )

#     def bayanaty_engine_capacities(self, payload: dict[str, Any]) -> dict[str, Any]:
#         return self._request(
#             method="POST",
#             path=self._with_company(self.BAYANATY_ENGINE_CAPACITIES_ENDPOINT),
#             json_payload=payload,
#             extra_headers=self._bayanaty_auth_headers(),
#         )

#     def bayanaty_trims(self, payload: dict[str, Any]) -> dict[str, Any]:
#         return self._request(
#             method="POST",
#             path=self._with_company(self.BAYANATY_TRIMS_ENDPOINT),
#             json_payload=payload,
#             extra_headers=self._bayanaty_auth_headers(),
#         )

#     def health_check(self) -> dict[str, Any]:
#         mock_payload = self.get_extra_config().get("mock_health_check")
#         if isinstance(mock_payload, dict):
#             return mock_payload
#         self.authenticate()
#         return {
#             "status": "ok",
#             "company_code": self._company_code(),
#             "masterdata_sets": {
#                 "body_types": len(load_body_type_records()),
#                 "cylinders": len(load_cylinder_records()),
#                 "nationalities": len(load_nationality_records()),
#                 "registration_locations": len(load_regn_location_records()),
#             },
#         }
from __future__ import annotations

import base64
from datetime import date, datetime
import logging
import re
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
    lookup_body_type_code,
    lookup_body_type_code_from_bayanaty,
    lookup_body_type_code_from_desc,
    lookup_cylinder_code,
    lookup_make_model_codes,
    lookup_nationality_code,
    lookup_regn_location_code,
)

logger = logging.getLogger(__name__)


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

    def _resolve_str(self, *candidates, default: str = "") -> str:
        """Return first non-empty, non-None candidate as a stripped string."""
        for c in candidates:
            if c is not None and str(c).strip() and str(c).strip().lower() != "none":
                return str(c).strip()
        return default

    def _with_company(self, path: str) -> str:
        separator = "&" if "?" in path else "?"
        if "company=" in path:
            return path
        return f"{path}{separator}company={self._company_code()}"

    def _ensure_success(self, payload: dict[str, Any]) -> dict[str, Any]:
        resp_code = str(payload.get("respCode", "")).strip()
        if resp_code and resp_code not in {"0", "200", "2000", "SUCCESS"}:
            raise ProviderRequestError(str(payload.get("errMessage") or f"QIC request failed with respCode {resp_code}."))
        return payload

    def _format_first_registration_date(self, value: Any) -> str:
        """
        QIC requires `firstRegDate` as `YYYY-MM-DD`, not future-dated.
        Accepts: date/datetime objects, ISO strings, or `YYYY`.
        """
        if value is None:
            return ""
        if isinstance(value, datetime):
            parsed = value.date()
        elif isinstance(value, date):
            parsed = value
        else:
            text = str(value).strip()
            if not text:
                return ""
            # Common ISO date formats: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS...
            try:
                parsed = datetime.fromisoformat(text.replace("Z", "+00:00")).date()
            except Exception:
                # Fallback: `YYYY` only
                if re.fullmatch(r"\d{4}", text):
                    parsed = date(int(text), 1, 1)
                else:
                    return ""

        if parsed > date.today():
            return ""
        return parsed.strftime("%d/%m/%Y")

    def _resolve_sum_insured(self, payload: dict[str, Any], vehicle: dict[str, Any]) -> float:
        sum_insured = float(
            payload.get("sum_insured") or vehicle.get("sum_insured") or 0
        )
        if sum_insured > 0:
            sum_insured = self._apply_minimum_sum_insured(sum_insured)
            return sum_insured

        vin = (
            vehicle.get("chassis_number")
            or payload.get("chassis_number")
            or vehicle.get("chassis_no")
            or payload.get("chassis_no")
        )
        if vin:
            try:
                val = self.bayanaty_vehicle_valuation({"Vin": vin})
                market_value = float(
                    val.get("marketValue")
                    or val.get("market_value")
                    or val.get("value")
                    or 0
                )
                if market_value > 0:
                    market_value = self._apply_minimum_sum_insured(market_value)
                    logger.info(
                        "QIC: resolved sum_insured=%.2f from Bayanaty for VIN=%s",
                        market_value, vin,
                    )
                    return market_value
            except Exception as e:
                logger.warning("QIC: Bayanaty valuation failed for VIN=%s: %s", vin, e)

        default_sum_insured = self.get_extra_config().get("default_sum_insured")
        if default_sum_insured not in (None, "", 0, "0"):
            default_value = float(default_sum_insured)
            default_value = self._apply_minimum_sum_insured(default_value)
            logger.warning(
                "QIC: sum_insured not found and Bayanaty failed; using default=%.2f",
                default_value,
            )
            return default_value

        return 0.0

    def _apply_minimum_sum_insured(self, sum_insured: float) -> float:
        """Enforce minimum sum_insured of 85000 AED."""
        QIC_MINIMUM_SUM_INSURED = float(self.get_extra_config().get("minimum_sum_insured") or 85000)
        if 0 < sum_insured < QIC_MINIMUM_SUM_INSURED:
            logger.warning(
                "QIC sum_insured=%.2f is below minimum %.2f; raising to minimum.",
                sum_insured,
                QIC_MINIMUM_SUM_INSURED,
            )
            return QIC_MINIMUM_SUM_INSURED
        return sum_insured

    def _resolve_first_registration_date(self, payload: dict[str, Any], vehicle: dict[str, Any]) -> str:
        # Priority requested by user: vehicle.first_registration_date OR registration_date OR manufacture_year/year.
        candidates = [
            vehicle.get("first_registration_date"),
            payload.get("first_registration_date"),
            vehicle.get("registration_date"),
            payload.get("reg_dt"),
            vehicle.get("registration_year"),
            vehicle.get("manufacture_year"),
            vehicle.get("year"),
            vehicle.get("model_year"),
            payload.get("model_year"),
        ]
        for candidate in candidates:
            formatted = self._format_first_registration_date(candidate)
            if formatted:
                return formatted

        # Final fallback: `{vehicle.year}-01-01`
        year = vehicle.get("year") or vehicle.get("model_year") or payload.get("model_year")
        try:
            year_int = int(str(year).strip())
        except Exception:
            year_int = 0
        result = ""

        if 1900 <= year_int <= date.today().year:
            return date(year_int, 1, 1).strftime("%d/%m/%Y")
        return ""
        
    
    
    def _format_date_ddmmyyyy(self, value: Any) -> str:
   
        if value is None:
            return ""
        if isinstance(value, datetime):
            return value.date().strftime("%d/%m/%Y")
        if isinstance(value, date):
            return value.strftime("%d/%m/%Y")
        text = str(value).strip()
        if not text:
            return ""
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00")).date()
            return parsed.strftime("%d/%m/%Y")
        except Exception:
            # Already in DD/MM/YYYY?
            if re.fullmatch(r"\d{2}/\d{2}/\d{4}", text):
                return text
            return ""
    

    def _build_tariff_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Build QIC tariff API request payload with EXACT field mapping per specification.
        
        Maps incoming quote request to QIC tariff endpoint with:
        - Masterdata lookups for codes (make, model, body_type, cylinder, nationality, registration)
        - Date formatting (DD/MM/YYYY)
        - Type conversions (integers for flags and counts)
        - Validation for required fields
        """
        customer = payload.get("customer") if isinstance(payload.get("customer"), dict) else payload
        vehicle = payload.get("vehicle") if isinstance(payload.get("vehicle"), dict) else payload

        # ========== MAKE AND MODEL CODES ==========
        make_code, model_code = lookup_make_model_codes(
            payload.get("make_id") or vehicle.get("make_id"),
            payload.get("model_id") or vehicle.get("model_id"),
        )

        # ========== SUM INSURED (VEHICLE VALUATION) ==========
        print(f"[QIC DEBUG] sum_insured resolution: payload={payload.get('sum_insured')!r}, vehicle={vehicle.get('sum_insured')!r}")
        sum_insured = self._resolve_sum_insured(payload, vehicle)
        print(f"[QIC DEBUG] sum_insured resolved to: {sum_insured}")

        if sum_insured <= 0:
            raise ProviderRequestError(
                "QIC requires sum_insured (vehicle valuation). "
                "Not found in payload, vehicle, Bayanaty valuation, or default config."
            )

        # ========== LOOKUPS ==========
        # Bug 2 fix: 3-step fallback for vehicle_type
        body_type_id = payload.get("body_type_id") or vehicle.get("body_type_id") or ""
        vehicle_type = lookup_body_type_code(body_type_id)
        if not vehicle_type:
            vehicle_type = lookup_body_type_code_from_bayanaty(body_type_id)
        if not vehicle_type:
            vehicle_type = lookup_body_type_code_from_desc(
                str(payload.get("body_type") or vehicle.get("body_type") or "")
            )
        
        # DEBUG: Log vehicle_usage resolution
        print(f"[QIC DEBUG] vehicle_usage raw: payload={payload.get('vehicle_usage')!r}, vehicle={vehicle.get('vehicle_usage')!r}")
        vehicle_usage = self._resolve_str(
            payload.get("vehicle_usage"),
            vehicle.get("vehicle_usage"),
            self.get_extra_config().get("default_vehicle_usage"),
            default="1001",  # Default: Private
        )
        print(f"[QIC DEBUG] vehicle_usage after fallback: {vehicle_usage!r}")

        no_of_cylinder = lookup_cylinder_code(
            payload.get("no_of_cylinder")
            or vehicle.get("no_of_cylinder")
            or vehicle.get("engine_capacity")
            or vehicle.get("engine_capacity_id")
        )
        nationality = lookup_nationality_code(payload.get("nationality") or customer.get("nationality"))
        regn_location = lookup_regn_location_code(payload.get("plate_source") or vehicle.get("plate_source"))
        if regn_location:
            regn_location = str(regn_location).zfill(3)  # '1' → '001'
                
        make_code, model_code = lookup_make_model_codes(
            payload.get("make_id") or vehicle.get("make_id"),
            payload.get("model_id") or vehicle.get("model_id"),
        )

        # Guard: ensure we got numeric codes, not raw name fallback
        if not make_code or not make_code.strip().isdigit():
            raise ProviderRequestError(
                f"QIC could not resolve a numeric makeCode. "
                f"make_id={payload.get('make_id') or vehicle.get('make_id')!r} "
                f"resolved to {make_code!r}. "
                f"Ensure make_id matches a valid QIC masterdata code or description."
    )

        # ========== DATES ==========
        import datetime as _pfd_dt
        _raw_policy_from = payload.get("policy_from_date") or payload.get("policyFromDate")
        _formatted_policy_from = self._format_date_ddmmyyyy(_raw_policy_from)
        try:
            _pfd_parsed = _pfd_dt.datetime.strptime(_formatted_policy_from, "%d/%m/%Y").date()
            policy_from_date = _formatted_policy_from if _pfd_parsed > _pfd_dt.date.today() else ""
        except Exception:
            policy_from_date = ""
        print(f"[QIC DEBUG] policyFromDate resolved to: {policy_from_date!r}")
        first_reg_date = self._resolve_first_registration_date(payload, vehicle)
        driver_dob = self._format_date_ddmmyyyy(payload.get("date_of_birth") or customer.get("date_of_birth"))

        # ========== BUILD TARIFF REQUEST WITH EXACT SPECIFICATION FIELDS ==========
        tariff_request = {
            "insuredName": str(customer.get("name") or payload.get("insured_name") or "Insured"),
            # "policyFromDate": policy_from_date,
            "makeCode": make_code,
            "modelCode": str(model_code)[:12],
            "modelYear": str(vehicle.get("model_year") or payload.get("model_year") or ""),
            "sumInsured": float(sum_insured),
            "vehicleType": str(vehicle_type or ""),
            "vehicleUsage": vehicle_usage,
            "noOfCylinder": str(no_of_cylinder or ""),
            "nationality": str(nationality or ""),
            "seatingCapacity": str(payload.get("seating_capacity") or vehicle.get("seating_capacity") or "5"),
            "firstRegDate": first_reg_date,
            "gccSpec": "1" if payload.get("is_gcc_spec") or vehicle.get("is_gcc_spec") else "0",
            "previousInsuranceValid": "1" if payload.get("previous_insurance_valid") else "0",
            "totalLoss": "1" if payload.get("total_loss") else "0",
            "driverDOB": driver_dob,
            "noClaimYear": str(int(payload.get("ncd_years") or vehicle.get("ncd_years") or 0)),
            "selfDeclarationYear": str(int(payload.get("self_declaration_year") or 0)),
            "chassisNo": str(payload.get("chassis_number") or vehicle.get("chassis_number") or ""),
            "driverExp": str(int(payload.get("driver_experience") or vehicle.get("driver_experience") or 0)),
            "admeId": int(self.get_extra_config().get("adme_id", payload.get("adme_id") or 401369)),
            "regnLocation": str(regn_location or ""),
            "geoArea": str(payload.get("geo_area") or self.get_extra_config().get("default_geo_area") or "1001"),
        }

        # If vehicle is less than 1 year old, noClaimYear must be 0
        import datetime as _dt
        _first_reg_str = tariff_request.get("firstRegDate") or ""
        print(f"[QIC DEBUG] firstRegDate for NCD reset check: {_first_reg_str!r}")
        if _first_reg_str:
            try:
                _first_reg_date = _dt.datetime.strptime(_first_reg_str, "%d/%m/%Y").date()
                _days_old = (_dt.date.today() - _first_reg_date).days
                print(f"[QIC DEBUG] vehicle age in days: {_days_old}")
                if _days_old < 365:
                    print(f"[QIC DEBUG] vehicle < 1 year old, resetting noClaimYear to 0")
                    tariff_request["noClaimYear"] = "0"
                    tariff_request["previousInsuranceValid"] = "0"
                else:
                    print(f"[QIC DEBUG] vehicle >= 1 year old, keeping noClaimYear={tariff_request.get('noClaimYear')!r}")
            except Exception as e:
                print(f"[QIC DEBUG] firstRegDate parse error: {e!r}")

        # ========== VALIDATION ==========
        unresolved_fields = []
        if not tariff_request.get("vehicleType"):
            unresolved_fields.append(f"vehicleType (body_type_id={payload.get('body_type_id') or vehicle.get('body_type_id')})")
        if not tariff_request.get("noOfCylinder"):
            unresolved_fields.append(f"noOfCylinder (engine_capacity_id or no_of_cylinder={payload.get('no_of_cylinder') or vehicle.get('no_of_cylinder') or vehicle.get('engine_capacity')})")
        if not tariff_request.get("regnLocation"):
            unresolved_fields.append(f"regnLocation (plate_source={payload.get('plate_source') or vehicle.get('plate_source')})")
        
        if unresolved_fields:
            raise ProviderRequestError(
                f"QIC tariff request has unresolved lookup fields: {', '.join(unresolved_fields)}. "
                f"These values did not match QIC masterdata. Check that the input data (body_type_id, engine_capacity_id, plate_source) "
                f"match valid QIC codes or descriptions."
            )

        # Sanitize: replace any literal "None" strings with empty string
        tariff_request = {
            k: ("" if isinstance(v, str) and v.strip().lower() == "none" else v)
            for k, v in tariff_request.items()
        }

        return tariff_request

    def get_tariff(self, payload: dict[str, Any]) -> dict[str, Any]:
        tariff_payload = self._build_tariff_request(payload)
        
        # Hard validation: Check all required fields are non-empty before sending to QIC
        required_non_empty = {
            'vehicleUsage': tariff_payload.get('vehicleUsage'),
            'vehicleType': tariff_payload.get('vehicleType'),
            'noOfCylinder': tariff_payload.get('noOfCylinder'),
            'makeCode': tariff_payload.get('makeCode'),
            'modelCode': tariff_payload.get('modelCode'),
            'nationality': tariff_payload.get('nationality'),
            'firstRegDate': tariff_payload.get('firstRegDate'),
            'driverDOB': tariff_payload.get('driverDOB'),
            'geoArea': tariff_payload.get('geoArea'),
            'regnLocation': tariff_payload.get('regnLocation'),
        }
        
        missing_fields = []
        for field, value in required_non_empty.items():
            if not str(value or '').strip():
                missing_fields.append(field)
        
        if missing_fields:
            raise ProviderRequestError(
                f"QIC tariff request is missing required fields: {', '.join(missing_fields)}. "
                f"These fields must be non-empty to proceed. Payload: {tariff_payload}"
            )
        
        # Validate sumInsured is positive
        try:
            sum_insured_value = float(tariff_payload.get('sumInsured') or 0)
            if sum_insured_value <= 0:
                raise ProviderRequestError(
                    f"QIC tariff request has invalid sumInsured={sum_insured_value} — must be > 0"
                )
        except (ValueError, TypeError) as e:
            raise ProviderRequestError(
                f"QIC tariff request has invalid sumInsured={tariff_payload.get('sumInsured')} — {e}"
            )
        
        print("QIC payload:", tariff_payload)
        response = self._request(
            method="POST",
            path=self._with_company(self.get_extra_config().get("tariff_endpoint", self.TARIFF_ENDPOINT)),
            json_payload=tariff_payload,
        )
        return self._ensure_success(response)

    def get_net_premium(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._request(
            method="POST",
            path=self._with_company(self.get_extra_config().get("net_premium_endpoint", self.NET_PREMIUM_ENDPOINT)),
            json_payload=payload,
        )
        return self._ensure_success(response)

    def send_payment_link(self, payload: dict[str, Any]) -> dict[str, Any]:
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
        response = self._request(
            method="POST",
            path=self._with_company(self.get_extra_config().get("policy_lookup_endpoint", self.POLICY_LOOKUP_ENDPOINT)),
            json_payload=payload,
        )
        return self._ensure_success(response)

    def get_quote(self, payload: dict[str, Any]):
        started = time.perf_counter()
        tariff = self.get_tariff(payload)
        quote_no = str(tariff.get("quoteNo") or tariff.get("quotationNo") or "")
        top_level_schemes = tariff.get("schemes") or []
        top_level_products = tariff.get("products") or []

        normalized_quotes: list[dict[str, Any]] = []

        if top_level_schemes and isinstance(top_level_schemes, list):
            if not quote_no:
                raise ProviderRequestError("QIC tariff response did not include quote number and schemes.")
            for scheme in top_level_schemes:
                premium_payload = {
                    "quoteNo": quote_no,
                    "schemes": [
                        {
                            "schemeCode": str(scheme.get("schemeCode") or ""),
                            "productCode": str(scheme.get("productCode") or ""),
                        }
                    ],
                }
                premium_data = self.get_net_premium(premium_payload)
                normalized_quotes.append(
                    {
                        "product": scheme,
                        "scheme": scheme,
                        "premium": premium_data,
                    }
                )

        elif top_level_products and isinstance(top_level_products, list):
            if not quote_no:
                raise ProviderRequestError("QIC tariff response did not include quote number and schemes.")
            for product in top_level_products:
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

        else:
            raise ProviderRequestError("QIC tariff response did not include quote number and schemes.")

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
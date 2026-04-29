from __future__ import annotations

import base64
import time
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from .base import BaseInsuranceProvider
from .dic_masterdata import list_masterdata, lookup_code
from .exceptions import ProviderAuthenticationError, ProviderRequestError


class DICProvider(BaseInsuranceProvider):
    AUTH_ENDPOINT = "/api/v1/User/Auth"
    GENERATE_QUOTE_ENDPOINT = "/api/v1/Insurance/GenerateQuote"
    CHOOSE_SCHEME_ENDPOINT = "/api/v1/Insurance/ChooseScheme"
    PAYMENT_INFO_ENDPOINT = "/api/v1/Insurance/GetPaymentInfo"
    DOCUMENT_TYPE_MAP = {
        "bank_lpo": {"code": "107", "name": "BankLpo"},
        "emirates_id_front": {"code": "103", "name": "Emirate ID Front"},
        "emirates_id_back": {"code": "105", "name": "Emirate ID Back"},
        "mulkiya_id_front": {"code": "101", "name": "Mulkiya ID Front"},
        "mulkiya_id_back": {"code": "102", "name": "Mulkiya ID Back"},
        "driving_license_front": {"code": "106", "name": "Driving License Front"},
        "driving_license_back": {"code": "121", "name": "Driving License Back"},
    }

    def __init__(self, provider_config):
        super().__init__(provider_config)
        self._token: str | None = None

    def _generate_request_id(self, provided: str | None = None) -> str:
        return provided or str(uuid.uuid4())

    def _request_headers(self, request_id: str) -> dict[str, str]:
        return {"X-REQUEST-ID": request_id}

    def _extract_message(self, payload: dict[str, Any]) -> str:
        message = payload.get("message")
        if isinstance(message, dict):
            return str(message.get("en") or message.get("ar") or "")
        if isinstance(message, str):
            return message
        return ""

    def _unwrap_response(self, payload: dict[str, Any]) -> Any:
        status_value = payload.get("status")
        if status_value not in (1, "1", True, None):
            detail = self._extract_message(payload) or "DIC request failed."
            raise ProviderRequestError(detail)
        return payload.get("data")

    def authenticate(self) -> str | None:
        if self._token:
            return self._token

        extra_config = self.get_extra_config()
        if "mock_token" in extra_config:
            self._token = str(extra_config["mock_token"])
            return self._token

        username = self.resolve_config_value("username", "")
        password = self.resolve_config_value("password", "")
        if not username or not password:
            raise ProviderAuthenticationError(
                "DIC requires username and password for authentication."
            )

        response = self._request(
            method="POST",
            path=extra_config.get("auth_endpoint", self.AUTH_ENDPOINT),
            json_payload={"userName": username, "password": password},
            authenticated=False,
            extra_headers=self._request_headers(self._generate_request_id()),
        )
        token = self._unwrap_response(response)
        if not token:
            raise ProviderAuthenticationError("DIC did not return a bearer token.")
        self._token = str(token)
        return self._token

    def _coerce_required_value(self, value: Any, field_name: str) -> str:
        text = str(value).strip() if value not in (None, "") else ""
        if not text:
            raise ProviderRequestError(f"DIC requires '{field_name}' in the quote payload.")
        return text

    def _format_date(self, value: Any) -> str:
        text = str(value).strip() if value not in (None, "") else ""
        if not text:
            return ""
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(text, fmt).strftime("%d/%m/%Y")
            except ValueError:
                continue
        return text

    def _format_mobile_number(self, value: Any) -> str:
        text = str(value).strip() if value not in (None, "") else ""
        if not text:
            return ""
        return text.replace("+", "").replace(" ", "")

    def _resolve_emirate_code(self, payload: dict[str, Any], customer: dict[str, Any], vehicle: dict[str, Any]) -> str:
        candidates = [
            payload.get("emirate"),
            customer.get("emirate"),
            payload.get("plate_source"),
            vehicle.get("plate_source"),
            payload.get("registration_location"),
            vehicle.get("registration_location"),
        ]
        for candidate in candidates:
            code = lookup_code("emirate", candidate)
            text = str(code).strip() if code not in (None, "") else ""
            if text:
                return text
        return ""

    def _normalize_document_list(self, payload: dict[str, Any]) -> list[dict[str, str]]:
        document_lists = payload.get("document_lists") or payload.get("documentLists") or []
        if not document_lists:
            document_lists = payload.get("documents") or []
        normalized: list[dict[str, str]] = []
        for item in document_lists:
            if not isinstance(item, dict):
                continue
            doc_mapping = self.DOCUMENT_TYPE_MAP.get(str(item.get("document_type") or "").strip())
            code = item.get("code") or (doc_mapping or {}).get("code")
            name = item.get("name") or (doc_mapping or {}).get("name")
            code = self._coerce_required_value(code, "document_lists[].code")
            name = self._coerce_required_value(name, "document_lists[].name")
            base64_value = item.get("base64")
            if not base64_value and item.get("content"):
                base64_value = base64.b64encode(item["content"]).decode("ascii")
            base64_text = self._coerce_required_value(base64_value, "document_lists[].base64")
            normalized.append(
                {
                    "code": code,
                    "name": name,
                    "base64": base64_text,
                    "type": str(item.get("type") or "png"),
                }
            )
        if not normalized:
            raise ProviderRequestError("DIC requires mandatory document uploads in document_lists.")
        return normalized

    def _build_generate_quote_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        customer = payload.get("customer") if isinstance(payload.get("customer"), dict) else payload
        vehicle = payload.get("vehicle") if isinstance(payload.get("vehicle"), dict) else payload

        insured_name = payload.get("insured_name") or customer.get("insured_name") or customer.get("name")
        nationality = lookup_code("nationality", payload.get("nationality") or customer.get("nationality"))
        gender = lookup_code("gender", payload.get("gender") or customer.get("gender"))
        emirate = self._resolve_emirate_code(payload, customer, vehicle)
        plate_code = lookup_code("plate_code", payload.get("plate_code") or vehicle.get("plate_code"))
        plate_source = lookup_code("plate_source", payload.get("plate_source") or vehicle.get("plate_source"))
        bank_name = lookup_code("bank_name", payload.get("bank_name") or vehicle.get("bank_name"))
        ncd_years = lookup_code("ncd_years", payload.get("ncd_years") or vehicle.get("ncd_years") or "0")
        traffic_type = lookup_code(
            "traffic_transaction_type",
            payload.get("traffic_tran_type") or vehicle.get("traffic_transaction_type"),
        )

        request_payload = {
            "insuredName": {
                "en": self._coerce_required_value(insured_name, "insured_name"),
                "ar": str(payload.get("insured_name_ar") or insured_name),
            },
            "nationality": self._coerce_required_value(nationality, "nationality"),
            "nationalId": self._coerce_required_value(
                payload.get("national_id")
                or customer.get("emirates_id")
                or customer.get("national_id"),
                "national_id",
            ),
            "idExpiryDt": self._coerce_required_value(
                self._format_date(
                    payload.get("id_expiry_dt")
                    or customer.get("emirates_id_expiry_date")
                    or customer.get("id_expiry_dt")
                ),
                "id_expiry_dt",
            ),
            "dateOfBirth": self._coerce_required_value(
                self._format_date(payload.get("date_of_birth") or customer.get("date_of_birth")),
                "date_of_birth",
            ),
            "gender": self._coerce_required_value(gender, "gender"),
            "emirate": self._coerce_required_value(emirate, "emirate"),
            "emailAddress": self._coerce_required_value(
                payload.get("email_address") or customer.get("email"),
                "email_address",
            ),
            "mobileNumber": self._coerce_required_value(
                self._format_mobile_number(
                    payload.get("mobile_number") or customer.get("mobile_number")
                ),
                "mobile_number",
            ),
            "licenseNo": self._coerce_required_value(
                payload.get("license_no") or vehicle.get("license_number"),
                "license_no",
            ),
            "licenseFmDt": self._coerce_required_value(
                self._format_date(payload.get("license_fm_dt") or vehicle.get("license_from_date")),
                "license_fm_dt",
            ),
            "licenseToDt": self._coerce_required_value(
                self._format_date(payload.get("license_to_dt") or vehicle.get("license_to_date")),
                "license_to_dt",
            ),
            "chassisNumber": self._coerce_required_value(
                payload.get("chassis_number") or vehicle.get("chassis_number"),
                "chassis_number",
            ),
            "regNumber": self._coerce_required_value(
                payload.get("reg_number") or vehicle.get("registration_number"),
                "reg_number",
            ),
            "regDt": self._coerce_required_value(
                self._format_date(payload.get("reg_dt") or vehicle.get("registration_date")),
                "reg_dt",
            ),
            "plateCode": self._coerce_required_value(plate_code, "plate_code"),
            "PlateSource": self._coerce_required_value(plate_source, "plate_source"),
            "tcfNumber": self._coerce_required_value(
                payload.get("tcf_number") or vehicle.get("tcf_number"),
                "tcf_number",
            ),
            "ncdYears": self._coerce_required_value(ncd_years, "ncd_years"),
            "trafficTranType": self._coerce_required_value(traffic_type, "traffic_tran_type"),
            "isVehBrandNew": "Y" if payload.get("is_veh_brand_new") or vehicle.get("is_vehicle_brand_new") else "N",
            "agencyRepairYn": "Y" if payload.get("agency_repair") or vehicle.get("agency_repair") else "N",
            "bankName": bank_name,
            "documentLists": self._normalize_document_list(payload),
        }
        request_payload["plateSource"] = request_payload["PlateSource"]
        return request_payload

    def generate_quote(self, payload: dict[str, Any], *, request_id: str | None = None) -> dict[str, Any]:
        request_id = self._generate_request_id(request_id or payload.get("request_id"))
        started = time.perf_counter()
        mock_payload = self.get_extra_config().get("mock_generate_quote_response")
        if isinstance(mock_payload, (dict, list)):
            return {
                "request_id": request_id,
                "response_time_ms": int((time.perf_counter() - started) * 1000),
                "data": mock_payload,
            }

        response = self._request(
            method="POST",
            path=self.get_extra_config().get("quote_endpoint", self.GENERATE_QUOTE_ENDPOINT),
            json_payload=self._build_generate_quote_request(payload),
            extra_headers=self._request_headers(request_id),
        )
        return {
            "request_id": request_id,
            "response_time_ms": int((time.perf_counter() - started) * 1000),
            "data": self._unwrap_response(response),
            "raw_response": response,
        }

    def choose_scheme(
        self,
        payload: dict[str, Any],
        *,
        request_id: str,
    ) -> dict[str, Any]:
        mock_payload = self.get_extra_config().get("mock_choose_scheme_response")
        if isinstance(mock_payload, dict):
            return mock_payload

        response = self._request(
            method="POST",
            path=self.get_extra_config().get("choose_scheme_endpoint", self.CHOOSE_SCHEME_ENDPOINT),
            json_payload=payload,
            extra_headers=self._request_headers(request_id),
        )
        return self._unwrap_response(response)

    def get_payment_info(
        self,
        *,
        request_id: str,
        tran_id: str | None = None,
    ) -> dict[str, Any]:
        mock_payload = self.get_extra_config().get("mock_payment_info_response")
        if isinstance(mock_payload, dict):
            return mock_payload

        params = {"tranId": tran_id} if tran_id else None
        response = self._request(
            method="GET",
            path=self.get_extra_config().get("payment_info_endpoint", self.PAYMENT_INFO_ENDPOINT),
            params=params,
            extra_headers=self._request_headers(request_id),
        )
        return self._unwrap_response(response)

    def _build_scheme_request(self, product: dict[str, Any]) -> dict[str, Any]:
        covers = product.get("covers") or {}
        mandatory = covers.get("mandatory") or []
        optional = covers.get("optional") or []
        return {
            "prodCode": str(product.get("prodCode") or ""),
            "covers": {
                "mandatory": ",".join(str(item.get("coverCode")) for item in mandatory if item.get("coverCode")),
                "optional": ",".join(str(item.get("coverCode")) for item in optional if item.get("coverCode")),
            },
        }

    def get_quote(self, payload: dict[str, Any]):
        started = time.perf_counter()
        mock_payload = self.get_extra_config().get("mock_quote_response")
        if isinstance(mock_payload, dict):
            return self.build_quote_from_mapping(
                mock_payload,
                response_time_ms=int((time.perf_counter() - started) * 1000),
            )

        quote_result = self.generate_quote(payload)
        products = quote_result.get("data") or []
        if not isinstance(products, list) or not products:
            raise ProviderRequestError("DIC did not return any quote products.")

        request_id = quote_result["request_id"]
        chosen_quotes: list[dict[str, Any]] = []
        for product in products:
            scheme_payload = self._build_scheme_request(product)
            if not scheme_payload["prodCode"]:
                continue
            scheme_data = self.choose_scheme(scheme_payload, request_id=request_id)
            chosen_quotes.append(
                {
                    "prodCode": scheme_payload["prodCode"],
                    "prodName": product.get("prodName"),
                    "quote": scheme_data,
                }
            )

        if not chosen_quotes:
            raise ProviderRequestError("DIC returned products but no selectable schemes.")

        best_quote = min(
            chosen_quotes,
            key=lambda item: Decimal(str((item.get("quote") or {}).get("netToCustomer", "0"))),
        )
        scheme_data = best_quote["quote"]
        return self.build_quote_from_mapping(
            {
                "premium": scheme_data.get("netPremium", scheme_data.get("grossPremium", 0)),
                "vat": scheme_data.get("vat", 0),
                "total": scheme_data.get("netToCustomer", scheme_data.get("grossPremium", 0)),
                "currency": "AED",
                "plan_name": scheme_data.get("scheme")
                or ((best_quote.get("prodName") or {}).get("en") if isinstance(best_quote.get("prodName"), dict) else best_quote.get("prodName"))
                or "DIC Plan",
                "request_id": request_id,
                "quotation_no": scheme_data.get("quotationNo"),
                "products": products,
                "selected_scheme": scheme_data,
            },
            response_time_ms=int((time.perf_counter() - started) * 1000),
        )

    def issue_policy(self, payload: dict[str, Any]) -> dict[str, Any]:
        request_id = self._generate_request_id(payload.get("request_id"))
        tran_id = payload.get("tran_id") or payload.get("quotation_no")
        return self.get_payment_info(request_id=request_id, tran_id=tran_id)

    def renew_policy(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.generate_quote(payload, request_id=payload.get("request_id"))

    def fetch_policy(self, payload: dict[str, Any]) -> dict[str, Any]:
        request_id = self._generate_request_id(payload.get("request_id"))
        tran_id = payload.get("tran_id") or payload.get("quotation_no") or payload.get("policy_no")
        return self.get_payment_info(request_id=request_id, tran_id=tran_id)

    def get_master_data(self, dataset: str) -> list[dict[str, str]]:
        return list_masterdata(dataset)

    def get_supported_master_data(self) -> dict[str, list[dict[str, str]]]:
        return {
            "bank_name": self.get_master_data("bank_name"),
            "emirate": self.get_master_data("emirate"),
            "gender": self.get_master_data("gender"),
            "nationality": self.get_master_data("nationality"),
            "ncd_years": self.get_master_data("ncd_years"),
            "plate_code": self.get_master_data("plate_code"),
            "plate_source": self.get_master_data("plate_source"),
            "traffic_transaction_type": self.get_master_data("traffic_transaction_type"),
        }

    def download_policy_documents(self, payload: dict[str, Any]) -> dict[str, Any]:
        payment_info = self.fetch_policy(payload)
        documents = payment_info.get("documents")
        return {
            "policy_no": payment_info.get("polNo"),
            "documents_base64": documents,
        }

    def health_check(self) -> dict[str, Any]:
        mock_payload = self.get_extra_config().get("mock_health_check")
        if isinstance(mock_payload, dict):
            return mock_payload
        token = self.authenticate()
        return {
            "status": "ok",
            "authenticated": bool(token),
            "masterdata_sets": sorted(self.get_supported_master_data().keys()),
        }
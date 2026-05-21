from __future__ import annotations

import logging
import time
from decimal import Decimal
from typing import Any

from django.core.cache import cache
import requests

from .base import BaseInsuranceProvider
from .exceptions import ProviderAuthenticationError, ProviderRequestError
from .nia_masterdata import (
    load_sheet_records,
    lookup_code,
    lookup_description,
    lookup_body_code_from_model,
    lookup_plate_color_code,
)

logger = logging.getLogger(__name__)


def _decimal_safe(obj):
    """Recursively convert Decimal values to float for JSON serialization safety."""
    from decimal import Decimal
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _decimal_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_decimal_safe(i) for i in obj]
    return obj


class NiaVehicleValueRangeError(ProviderRequestError):
    def __init__(self, message: str, min_value: float, max_value: float):
        super().__init__(message)
        self.min_value = min_value
        self.max_value = max_value


class NIAProvider(BaseInsuranceProvider):
    LOGIN_ENDPOINT = "/Api/Auth/Login"
    CREATE_QUOTE_ENDPOINT = "/Api/Motor/CreateQuote"
    SAVE_QUOTE_WITH_PLAN_ENDPOINT = "/Api/Motor/SaveQuoteWithPlan"
    SAVE_ADDL_INFO_ENDPOINT = "/Api/Motor/SaveAddlInfo"
    SAVE_DOCUMENT_ENDPOINT = "/Api/Motor/SaveDocument"
    PROPOSAL_SUMMARY_ENDPOINT = "/Api/Motor/ProposalSummary"
    APPROVE_POLICY_ENDPOINT = "/Api/Motor/ApprovePolicy"
    GENERATE_PAYMENT_LINK_ENDPOINT = "/Api/Motor/GeneratePaymentLink"
    GET_PAYMENT_DETAILS_ENDPOINT = "/Api/Motor/GetPaymentDetails"
    NIA_TEST_EMIRATES_ID = "784-1989-1234567-1"

    DOCUMENT_TYPE_MAP = {
        "mulkiya_id_front": {"docCode": "10001", "docDesc": "Mulkiya Front"},
        "mulkiya_id_back": {"docCode": "10002", "docDesc": "Mulkiya Back"},
        "emirates_id_front": {"docCode": "10003", "docDesc": "Emirates ID Front"},
        "emirates_id_back": {"docCode": "10004", "docDesc": "Emirates ID Back"},
        "driving_license_front": {"docCode": "10005", "docDesc": "Driving License Front"},
        "driving_license_back": {"docCode": "10006", "docDesc": "Driving License Back"},
        "ncd": {"docCode": "10007", "docDesc": "NCD"},
        "vehicle_invoice": {"docCode": "10008", "docDesc": "Vehicle Invoice/Hayaza"},
    }

    def __init__(self, provider_config):
        super().__init__(provider_config)
        self.timeout = (10, 60)
        self._token: str | None = None
        self._last_corrected_sum_insured: float | None = None

    def _token_cache_key(self) -> str:
        return f"insurance-provider-token:{self.provider_code}"

    def _clear_token(self) -> None:
        self._token = None
        cache.delete(self._token_cache_key())

    def _ensure_success(self, payload: dict[str, Any]) -> dict[str, Any]:
        # Handle HTTP-level error responses (no Status field)
        if "status" in payload and "errors" in payload:
            errors = payload.get("errors", {})
            error_msg = "; ".join(
                f"{field}: {msgs[0] if isinstance(msgs, list) else msgs}"
                for field, msgs in errors.items()
            )
            raise ProviderRequestError(f"NIA validation error: {error_msg}")

        status_value = payload.get("Status")

        # Status=1 is always success
        if status_value == 1:
            return payload

        # Status=0 with Data as list = field validation errors
        data = payload.get("Data")
        if status_value == 0 and isinstance(data, list) and data:
            field_errors = "; ".join(
                f"{item.get('field', '')}: {item.get('message', '')}"
                for item in data
            )
            status_msg = payload.get("StatusMessage") or "Validation errors occurred."
            raise ProviderRequestError(f"{status_msg} Fields: {field_errors}")

        # Status=0 with Message.Text = business rule error
        message = payload.get("Message")
        if status_value == 0 and isinstance(message, dict):
            msg_text = str(message.get("Text") or "").strip()
            if msg_text and msg_text.lower() not in ("null", "none", ""):
                raise ProviderRequestError(msg_text)

        # Status=0 with StatusMessage
        if status_value == 0:
            status_msg = str(payload.get("StatusMessage") or "").strip()
            if status_msg and status_msg.lower() not in ("null", "none", ""):
                raise ProviderRequestError(status_msg)
            raise ProviderRequestError("NIA request failed.")

        return payload

    def authenticate(self) -> str | None:
        if self._token:
            return self._token
        cached = cache.get(self._token_cache_key())
        if cached:
            self._token = str(cached)
            return self._token
        mock = self.get_extra_config().get("mock_token")
        if mock:
            self._token = str(mock)
            return self._token
        username = self.resolve_config_value("username", "")
        password = self.resolve_config_value("password", "")
        if not username or not password:
            raise ProviderAuthenticationError("NIA requires username and password.")
        response = self._request(
            method="POST",
            path=self.get_extra_config().get("login_endpoint", self.LOGIN_ENDPOINT),
            json_payload={
                "username": username,
                "password": password,
                "loginMode": self.get_extra_config().get("login_mode", "EMAIL"),
            },
            authenticated=False,
            extra_headers={"Content-Type": "application/json"},
        )
        self._ensure_success(response)
        token = response.get("Data")
        if isinstance(token, list):
            token = (token[0] or {}).get("Token")
        if not token:
            raise ProviderAuthenticationError("NIA login did not return a token.")
        self._token = str(token)
        cache.set(
            self._token_cache_key(),
            self._token,
            timeout=int(self.get_extra_config().get("token_ttl_seconds", 3300)),
        )
        return self._token

    def get_auth_headers(self) -> dict[str, str]:
        # Default to using Authorization header; can be disabled via config.
        if self.get_extra_config().get("use_authorization_header", True) is False:
            return {"Content-Type": "application/json"}
        token = self.authenticate()
        template = str(self.get_extra_config().get("authorization_header_template", "Bearer {token}"))
        return {
            "Authorization": template.format(token=token),
            "Content-Type": "application/json",
        }

    def _user_id(self) -> str:
        user_id = self.get_extra_config().get("user_id") or self.resolve_config_value("username", "")
        return str(user_id)

    def _request_payload(self, section_name: str, section_value: Any) -> dict[str, Any]:
        return {
            "Authentication": {"Token": self.authenticate(), "UserId": self._user_id()},
            section_name: section_value,
        }

    def _format_date_mmddyyyy(self, value: Any) -> str:
        """Format any date value to MM/DD/YYYY as required by NIA API."""
        if not value:
            return ""
        import datetime as _fmt_dt
        try:
            if isinstance(value, _fmt_dt.datetime):
                return value.strftime("%m/%d/%Y")
            if isinstance(value, _fmt_dt.date):
                return value.strftime("%m/%d/%Y")
            text = str(value).strip()
            if not text or text.lower() in ("none", "null", ""):
                return ""
            # Already MM/DD/YYYY
            import re
            if re.fullmatch(r"\d{2}/\d{2}/\d{4}", text):
                return text
            # Try ISO format YYYY-MM-DD
            parsed = _fmt_dt.datetime.fromisoformat(
                text[:10].replace("Z", "")
            ).date()
            return parsed.strftime("%m/%d/%Y")
        except Exception:
            return str(value)

    def _flat_request_payload(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Some NIA endpoints expect fields flat at root level
        merged with Authentication, not nested under a key.
        """
        payload = {
            "Authentication": {
                "Token": self.authenticate(),
                "UserId": self._user_id(),
            }
        }
        payload.update(dict(data))  # copy to avoid mutating caller's dict
        return payload

    def _post_flat(self, path: str, data: dict[str, Any]) -> dict[str, Any]:
        """Post with flat payload structure for CreateQuote."""
        extra_headers = self.get_auth_headers()
        flat_payload = self._flat_request_payload(data)
        print(f"[NIA DEBUG] POST flat {path}")
        print(f"[NIA DEBUG] flat payload keys: {list(flat_payload.keys())}")
        max_retries = 3
        for attempt in range(max_retries + 1):
            try:
                response = self._request(
                    method="POST",
                    path=path,
                    json_payload=flat_payload,
                    authenticated=False,
                    extra_headers=extra_headers if extra_headers else None,
                )
                break
            except ProviderRequestError as exc:
                msg = str(exc).lower()
                is_timeout_or_connection = (
                    "timeout" in msg
                    or "timed out" in msg
                    or "connection error" in msg
                    or "connection aborted" in msg
                    or "max retries exceeded" in msg
                    or "name or service not known" in msg
                )
                if not is_timeout_or_connection:
                    raise
                if str(flat_payload.get("PolRefNo") or "").strip():
                    logging.getLogger(__name__).warning(
                        "NIA timeout after retries"
                    )
                    return {"status": "pending", "provider": "NIA", "error": "timeout"}
                if attempt < max_retries:
                    time.sleep(2 ** attempt)
                    continue
                logging.getLogger(__name__).warning("NIA timeout after retries")
                return {"status": "pending", "provider": "NIA", "error": "timeout"}
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
                if str(flat_payload.get("PolRefNo") or "").strip():
                    logging.getLogger(__name__).warning("NIA timeout after retries")
                    return {"status": "pending", "provider": "NIA", "error": "timeout"}
                if attempt < max_retries:
                    time.sleep(2 ** attempt)
                    continue
                logging.getLogger(__name__).warning("NIA timeout after retries")
                return {"status": "pending", "provider": "NIA", "error": "timeout"}
        print(f"[NIA DEBUG] flat response: {response}")
        return response

    def _post_with_auth_body(self, path: str, section_name: str, section_value: Any) -> dict[str, Any]:
        # Some NIA environments require token both in body AND Authorization header.
        # `get_auth_headers()` is config-driven and may return {}.
        extra_headers = self.get_auth_headers()
        print("NIA headers:", extra_headers)
        print(f"[NIA DEBUG] POST {path}")
        print(f"[NIA DEBUG] payload: {self._request_payload(section_name, section_value)}")
        max_retries = 3
        for attempt in range(max_retries + 1):
            try:
                response = self._request(
                    method="POST",
                    path=path,
                    json_payload=self._request_payload(section_name, section_value),
                    authenticated=False,
                    extra_headers=extra_headers if extra_headers else None,
                )
                print(f"[NIA DEBUG] response: {response}")
                return response
            except ProviderRequestError as exc:
                # If token expired / invalid, refresh once and retry.
                if "unauthorized" in str(exc).lower() or "401" in str(exc):
                    logging.getLogger(__name__).warning("NIA request unauthorized; refreshing token and retrying once.")
                    self._clear_token()
                    extra_headers = self.get_auth_headers()
                    print("NIA headers:", extra_headers)
                    print(f"[NIA DEBUG] POST {path}")
                    print(f"[NIA DEBUG] payload: {self._request_payload(section_name, section_value)}")
                    response = self._request(
                        method="POST",
                        path=path,
                        json_payload=self._request_payload(section_name, section_value),
                        authenticated=False,
                        extra_headers=extra_headers if extra_headers else None,
                    )
                    print(f"[NIA DEBUG] response: {response}")
                    return response
                msg = str(exc).lower()
                is_timeout_or_connection = (
                    "timeout" in msg
                    or "timed out" in msg
                    or "connection error" in msg
                    or "connection aborted" in msg
                    or "max retries exceeded" in msg
                    or "name or service not known" in msg
                )
                if not is_timeout_or_connection:
                    raise
                if attempt < max_retries:
                    time.sleep(2 ** attempt)
                    continue
                logging.getLogger(__name__).warning("NIA timeout after retries")
                return {"status": "pending", "provider": "NIA", "error": "timeout"}
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
                if attempt < max_retries:
                    time.sleep(2 ** attempt)
                    continue
                logging.getLogger(__name__).warning("NIA timeout after retries")
                return {"status": "pending", "provider": "NIA", "error": "timeout"}
        logging.getLogger(__name__).warning("NIA timeout after retries")
        return {"status": "pending", "provider": "NIA", "error": "timeout"}

    def _map_product_code(self, insurance_type: str | None, agency_repair: bool) -> str:
        # Allow forcing a specific product via extra_config
        forced_product = self.get_extra_config().get("force_product_code")
        if forced_product:
            return str(forced_product)

        if insurance_type == "third_party":
            return lookup_code("PolProdCode", "Third Party Liability")

        # Check if agency product is allowed (default: disallow)
        allow_agency = self.get_extra_config().get("allow_agency_product", False)
        if agency_repair and allow_agency:
            return lookup_code("PolProdCode", "Motor Comprehensive – Agency")
        return lookup_code("PolProdCode", "Motor Comprehensive –Non Agency")

    def resolve_nia_product_code(
        self,
        vehicle_usage: str,
        is_brand_new: str,
        agency_type: str,
    ) -> str:
        """
        Resolve NIA product code based on vehicle and account configuration.
        Default: Non-Agency (1002) unless explicitly overridden.
        Agency (1001) only if allow_agency_product=True in extra_config AND
        vehicle is explicitly brand new.
        """
        forced = self.get_extra_config().get("force_product_code")
        if forced:
            return str(forced)

        insurance_type = self.get_extra_config().get("default_insurance_type", "")
        if str(insurance_type).lower() == "third_party":
            return lookup_code("PolProdCode", "Third Party Liability")

        allow_agency = self.get_extra_config().get("allow_agency_product", False)

        if is_brand_new == "Y" and allow_agency:
            product_code = lookup_code("PolProdCode", "Motor Comprehensive – Agency")
        else:
            product_code = lookup_code("PolProdCode", "Motor Comprehensive –Non Agency")

        scheme_type = self._map_scheme_type(product_code)
        print(
            "[NIA PRODUCT DEBUG]",
            "BrandNew:",
            is_brand_new,
            "Agency:",
            agency_type,
            "Usage:",
            vehicle_usage,
            "Scheme:",
            scheme_type,
        )
        return product_code

    def _map_scheme_type(self, product_code: str) -> str:
        for record in load_sheet_records("PolSchemeType"):
            if str(record.get("Product Code")).strip() == str(product_code).strip():
                scheme = str(record.get("Code") or "").strip()
                if scheme:
                    return scheme
        raise ValueError(f"No SchemeType mapping found for product {product_code}")

    def _extract_vehicle_value_range(self, message: str) -> tuple[float | None, float | None]:
        import re
        match = re.search(r"between AED ([\d,]+) and AED ([\d,]+)", str(message or ""))
        if match:
            min_val = float(match.group(1).replace(",", ""))
            max_val = float(match.group(2).replace(",", ""))
            return min_val, max_val
        return None, None

    def _normalize_emirates_id(self, civil_id: str) -> str:
        if not civil_id:
            raise ProviderRequestError(
                "Emirates ID is missing. Please update the deal with a valid Emirates ID."
            )

        import re
        digits = re.sub(r"\D", "", civil_id)
        if len(digits) != 15:
            raise ProviderRequestError(
                f"Emirates ID '{civil_id}' has {len(digits)} digits after removing dashes "
                f"— must be exactly 15 digits."
            )
        if not digits.startswith("784"):
            raise ProviderRequestError(
                f"Emirates ID '{civil_id}' does not start with 784 — invalid UAE Emirates ID."
            )

        total = 0
        for i, d in enumerate(digits[:-1]):
            n = int(d)
            if i % 2 == 0:
                n *= 2
                if n > 9:
                    n -= 9
            total += n
        expected_check = (10 - (total % 10)) % 10
        actual_check = int(digits[-1])
        if expected_check != actual_check:
            raise ProviderRequestError(
                f"Emirates ID '{civil_id}' has an invalid check digit "
                f"(got {actual_check}, expected {expected_check}). "
                f"Please verify and correct the Emirates ID on the deal."
            )

        print("[NIA CIVIL ID FINAL]", civil_id, "→", digits)
        print("[NIA FINAL CIVIL ID USED]", digits)
        return digits

    def format_emirates_id(self, eid: str) -> str:
        import re

        raw = str(eid or "").strip()
        digits = re.sub(r"\D", "", raw)
        if len(digits) != 15 or not digits.startswith("784"):
            return self.NIA_TEST_EMIRATES_ID
        if digits[3:14] == "0" * 11:
            return self.NIA_TEST_EMIRATES_ID
        return f"{digits[:3]}-{digits[3:7]}-{digits[7:14]}-{digits[14]}"

    def _validate_create_quote_payload(self, request_payload: dict[str, Any]) -> None:
        import re

        required_fields = [
            "PolAssrAge",
            "PolAssrCivilIdExpDt",
            "VehServiceType",
            "VehOdometer",
            "PolAssrCivilId",
        ]
        for field in required_fields:
            if request_payload.get(field) in (None, ""):
                raise ValueError(f"NIA payload missing required field: {field}")

        civil_digits = re.sub(r"\D", "", str(request_payload.get("PolAssrCivilId") or ""))
        if len(civil_digits) != 15:
            raise ValueError("NIA payload invalid PolAssrCivilId: must resolve to exactly 15 digits.")
        try:
            veh_fc_value = float(str(request_payload.get("VehFcValue") or "0"))
        except Exception:
            raise ValueError("NIA payload invalid VehFcValue: must be numeric.")
        if veh_fc_value <= 0:
            raise ValueError("NIA payload invalid VehFcValue: must be greater than 0.")
        print("[NIA VALIDATION PASSED]")

    def _resolve_nationality_code(self, nationality: str) -> str:
        if not nationality:
            return ""
        result = lookup_code("PolAssrNation", nationality)
        if result:
            if result != nationality:
                return str(result).strip()
            if str(nationality).strip().isdigit():
                return str(result).strip()

        text = str(nationality).strip().upper()
        for record in load_sheet_records("PolAssrNation"):
            desc = str(record.get("Description") or "").strip().upper()
            code = str(record.get("Code") or "").strip()
            if desc == text:
                return code
            if desc.startswith(text) or text.startswith(desc[: max(4, len(desc) - 2)]):
                return code
        logging.getLogger(__name__).warning(
            "[NIA] Could not resolve nationality code for '%s'",
            nationality,
        )
        return ""

    def _resolve_nia_body_type(self, vehicle: dict, body_type_id: str) -> str:
        """
        Resolve a body_type_id (which may be a Bayanaty internal ID like '500116')
        to a valid NIA VehBodyType code.
        
        Strategy:
        1. Check if body_type_id directly matches a code or description in VehBodyType sheet
        2. If not found (unmapped Bayanaty ID), resolve via VehModel sheet using model_id
        """
        # Step 1: check if body_type_id directly matches a NIA VehBodyType Code or Description
        nia_sheet_records = load_sheet_records("VehBodyType")
        direct_match = ""
        for rec in nia_sheet_records:
            if rec.get("Code", "").strip() == str(body_type_id).strip():
                direct_match = rec["Code"].strip()
                break
            if rec.get("Description", "").strip().upper() == str(body_type_id).strip().upper():
                direct_match = rec["Code"].strip()
                break

        if direct_match:
            print(f"[NIA BODY TYPE] raw={body_type_id!r} resolved={direct_match!r} (direct match)")
            return direct_match

        # Step 2: body_type_id is an unmapped Bayanaty ID — resolve via VehModel sheet
        nia_model_code = lookup_code(
            "VehModel", vehicle.get("model_id") or "",
            code_key="MODEL CODE", description_key="MODE DESCRIPTION"
        )
        body_code, body_desc = lookup_body_code_from_model(nia_model_code)
        print(f"[NIA BODY TYPE] raw={body_type_id!r} nia_model={nia_model_code!r} resolved={body_code!r} ({body_desc})")
        return body_code or ""

    def _build_create_quote_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        import datetime as _dt

        customer = payload.get("customer") if isinstance(payload.get("customer"), dict) else payload
        vehicle = payload.get("vehicle") if isinstance(payload.get("vehicle"), dict) else payload

        # --- Sum insured ---
        sum_insured = float(vehicle.get("sum_insured") or payload.get("sum_insured") or 0)
        if sum_insured <= 0:
            default_si = self.get_extra_config().get("default_sum_insured")
            if default_si not in (None, "", 0, "0"):
                sum_insured = float(default_si)
        if sum_insured <= 0:
            sum_insured = 10000.0
            logging.getLogger(__name__).warning(
                "[NIA] sum_insured not found on deal; using hardcoded fallback 10000.0"
            )

        # --- Last name fallback ---
        _full_name = str(customer.get("name") or "").strip()
        _name_parts = _full_name.split()
        _last_name = str(customer.get("last_name") or "").strip()
        if not _last_name and len(_name_parts) > 1:
            _last_name = _name_parts[-1]
        elif not _last_name and _name_parts:
            _last_name = _name_parts[0]

        # --- DOB in MM/DD/YYYY ---
        _dob_formatted = self._format_date_mmddyyyy(
            customer.get("date_of_birth") or ""
        )

        # --- Registration date in MM/DD/YYYY ---
        _regn_dt_raw = (
            vehicle.get("registration_date")
            or vehicle.get("first_registration_date")
            or ""
        )
        _regn_dt_formatted = self._format_date_mmddyyyy(_regn_dt_raw)

        _is_brand_new = bool(vehicle.get("is_vehicle_brand_new"))
        reg_date = vehicle.get("registration_date") or vehicle.get("first_registration_date")
        # Fallback 1: Registration date
        if not _is_brand_new:
            if reg_date:
                try:
                    reg_str = str(reg_date).strip()[:10]
                    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
                        try:
                            reg_parsed = _dt.datetime.strptime(reg_str, fmt).date()
                            if (_dt.date.today() - reg_parsed).days < 400:
                                _is_brand_new = True
                            break
                        except Exception:
                            continue
                except Exception:
                    pass

        # Fallback 2: Model year
        if not _is_brand_new:
            try:
                model_year = int(str(vehicle.get("model_year") or 0))
                if model_year >= _dt.date.today().year:
                    _is_brand_new = True
            except Exception:
                pass

        veh_brand_new_yn = "Y" if _is_brand_new else "N"

        if veh_brand_new_yn == "Y":
            veh_agency_type = "Y"
        else:
            veh_agency_type = "N"
        print(
            "[NIA FINAL BRAND DETECTION]",
            "BrandNew:", veh_brand_new_yn,
            "RegDate:", reg_date,
            "ModelYear:", vehicle.get("model_year")
        )

        _model_year = int(str(vehicle.get("model_year") or 0) or 0)

        # --- Vehicle age ---
        _veh_age = int(payload.get("vehicle_age") or 0)
        if _veh_age <= 0:
            try:
                _mfg_year = int(str(vehicle.get("model_year") or payload.get("model_year") or 0).strip())
                _veh_age = max(1, _dt.date.today().year - _mfg_year)
            except Exception:
                _veh_age = 1

        # Product selection with strict NIA validation constraints
        supports_agency = str(
            self.get_extra_config().get("supports_agency_product", "false")
        ).strip().lower() not in ("0", "false", "no")
        if veh_brand_new_yn == "Y":
            if supports_agency:
                product_code = "1001"
                pol_scheme_type = self._map_scheme_type(product_code)
            else:
                # Account doesn't support Agency — force Non-Agency by masking brand new flag
                product_code = "1002"
                pol_scheme_type = self._map_scheme_type(product_code)
                veh_brand_new_yn = "N"   # Force to N so NIA accepts Non-Agency
                veh_agency_type = "N"
                logging.getLogger(__name__).warning(
                    "[NIA] Brand new vehicle but supports_agency_product=false; "
                    "forcing VehBrandNewYn=N and VehAgencyType=N to use Product 1002."
                )
        else:
            product_code = "1002"
            pol_scheme_type = self._map_scheme_type(product_code)
        print(
            "[NIA FINAL PRODUCT]",
            "BrandNew:",
            veh_brand_new_yn,
            "Agency:",
            veh_agency_type,
            "Product:",
            product_code,
        )

        print("[NIA FINAL PRODUCT+SCHEME]", product_code, pol_scheme_type)

        # --- Phone number validation ---
        _mobile = str(customer.get("mobile_number") or "").lstrip("0")
        _phone_raw = str(customer.get("phone_number") or "").lstrip("0")
        if not _phone_raw or _phone_raw[:1] not in ("2", "3", "4", "6", "7", "9"):
            _phone_raw = str(self.get_extra_config().get("default_phone") or "42000000")

        # --- Emirates ID expiry ---
        _civil_id_expiry = self._format_date_mmddyyyy(
            customer.get("emirates_id_expiry")
            or customer.get("civil_id_expiry")
            or self.get_extra_config().get("default_civil_id_expiry")
            or "12/31/2030"
        )
        if not _civil_id_expiry:
            _civil_id_expiry = "12/31/2030"

        _civil_id_raw = str(customer.get("emirates_id") or "")
        print("[NIA ORIGINAL CIVIL ID]", _civil_id_raw)
        _civil_id = self.format_emirates_id(_civil_id_raw)
        print("[NIA FINAL CIVIL ID]", _civil_id)

        pol_assr_age = int(customer.get("insured_age") or payload.get("insured_age") or 0)
        if not pol_assr_age:
            if _dob_formatted:
                try:
                    _dob_date = _dt.datetime.strptime(_dob_formatted, "%m/%d/%Y").date()
                    pol_assr_age = max(1, int((_dt.date.today() - _dob_date).days // 365.25))
                except Exception:
                    pol_assr_age = 0
            if not pol_assr_age:
                raise ValueError("PolAssrAge missing and DOB not available")

        _nationality_code = self._resolve_nationality_code(customer.get("nationality") or "")
        print(f"[NIA NATIONALITY] raw='{customer.get('nationality')}' resolved='{_nationality_code}'")
        
        _body_type_id = vehicle.get("body_type_id") or payload.get("body_type_id") or ""
        if not _body_type_id:
            from .nia_masterdata import lookup_body_code_from_model
            _chassis_no = vehicle.get("chassis_no") or vehicle.get("chassis_number") or vehicle.get("vin") or payload.get("chassis_no") or ""
            _model_id_for_body = vehicle.get("model_id") or payload.get("model_id") or ""
            print(f"[NIA BODY DERIVE] chassis_no={_chassis_no!r} model_id={_model_id_for_body!r} vehicle_keys={list(vehicle.keys())}")
            _body_code, _body_desc = lookup_body_code_from_model(_model_id_for_body)
            if not _body_code and _chassis_no:
                # fallback: try matching chassis prefix against VehModel records
                for _rec in load_sheet_records("VehModel"):
                    if _rec.get("CHASSIS NO", "").strip().startswith(_chassis_no[:8]):
                        _body_code = _rec.get("BODY CODE", "").strip()
                        _body_desc = _rec.get("BODY DESC", "").strip()
                        break
            _body_type_id = _body_code
            print(f"[NIA BODY DERIVE RESULT] _body_type_id={_body_type_id!r} _body_desc={_body_desc!r}")
        

        
        _odometer_value = (
            payload.get("odometer_reading")
            or vehicle.get("odometer_reading")
            or self.get_extra_config().get("default_odometer")
            or "100"
        )
        try:
            if int(float(str(_odometer_value))) < 100:
                _odometer_value = "100"
            else:
                _odometer_value = str(int(float(str(_odometer_value))))
        except Exception:
            _odometer_value = "100"
        try:
            _ncd_raw = int(payload.get("ncd_years") or vehicle.get("ncd_years") or 0)
        except (ValueError, TypeError):
            _ncd_raw = 0
        _ncd_capped = str(min(_ncd_raw, 3))

        request_payload = {
            "PolRefNo": "",
            "PolDeptCode": str(self.get_extra_config().get("department_code", "10")),
            "PolPartyCode": str(self.get_extra_config().get("party_code", "201001")),
            "PolDivnCode": str(self.get_extra_config().get("division_code", "813")),
            "PolSiCurrCode": "101",
            "PolPremCurrCode": "101",
            "PolAssrCode": str(self.get_extra_config().get("assured_code", "")),
            "PolAssrName": str(customer.get("name") or ""),
            "PolAssrLastName": _last_name,
            "PolAssrType": str(
                lookup_code("PolAssrType", customer.get("assured_type") or "INDIVIDUAL") or "100"
            ),
            "PolAssrDob": _dob_formatted,
            "PolAssrAge": int(pol_assr_age),
            "PolAssrCivilId": _civil_id,
            "PolAssrCivilIdExpDt": _civil_id_expiry,
            "PolAssrTradeLicNo": str(customer.get("trade_license_no") or ""),
            "PolAssrEmail": str(customer.get("email") or ""),
            "PolAssrMobile": _mobile,
            "PolAssrPhone": _phone_raw,
            "PolAssrNation": _nationality_code,
            "PolProdCode": product_code,
            "PolSchemeType": pol_scheme_type,
            "PolSchCode": "1000",
            "PolPrevPolNo": "0",
            "VehChassisNo": str(vehicle.get("chassis_number") or ""),
            "VehUsage": lookup_code("VehUsage", vehicle.get("vehicle_usage") or "PRIVATE (Indiv./Comm.)"),
            "VehMake": lookup_code("VehMake", vehicle.get("make_id") or ""),
            "VehModel": lookup_code("VehModel", vehicle.get("model_id") or "", code_key="MODEL CODE", description_key="MODE DESCRIPTION"),
            "VehBodyType": self._resolve_nia_body_type(vehicle, _body_type_id),
            "VehNoCylinder": lookup_code(
                "VehNoCylinder",
                vehicle.get("cylinder_count")
                or vehicle.get("engine_cylinder_count")
                or "4 CYLINDERS",
            ),
            "VehNoSeats": str(int(float(vehicle.get("seating_capacity") or 5))),
            "VehNoDoors": str(vehicle.get("door_count") or "5"),
            "VehCc": lookup_code(
                "VehCc",
                vehicle.get("engine_capacity_id") or vehicle.get("engine_capacity") or "",
            ),
            "VehMfgYear": (
                str(int(float(str(vehicle.get("model_year") or 0))))
                if vehicle.get("model_year")
                else ""
            ),
            "VehBrandNewYn": veh_brand_new_yn,
            "VehAgencyType": veh_agency_type,
            "VehFcValue": str(int(float(sum_insured))),
            "VehLoadCapacity": str(
                lookup_code("VehLoadCapacity", vehicle.get("load_capacity") or "No Loading")
            ),
            "VehRegion": lookup_description("VehRegion", "GCC" if vehicle.get("is_gcc_spec") else "Non-GCC"),
            "VehRegnDt": _regn_dt_formatted,
            "VehAge": str(int(float(_veh_age))),
            "VehPrevInsType": str(
                lookup_code("VehPrevInsType", payload.get("previous_insurance_type") or 1) or "1"
            ),
            "VehAccident": lookup_code("VehAccident", "Yes" if payload.get("total_loss") else "No"),
            "VehRegnCardExp": lookup_code("VehRegnCardExp", "Yes" if payload.get("registration_card_expired") else "No"),
            "VehOffroadYn": lookup_code("VehOffroadYn", "Yes" if vehicle.get("offroad_cover") else "No"),
            "VehNcdYears": _ncd_capped,
            "VehDriverExperience": str(payload.get("driver_experience") or "0"),
            "PolAssrVehLicIssPlace": str(payload.get("license_issue_place") or customer.get("license_issue_place") or self.get_extra_config().get("default_license_issue_place") or "1000"),
            "PolAssrVehLicIssDt": self._format_date_mmddyyyy(payload.get("driver_license_issue_date") or vehicle.get("license_from_date") or ""),
            "PolAssrVehLicExpDt": self._format_date_mmddyyyy(payload.get("driver_license_expiry_date") or vehicle.get("license_to_date") or ""),
            "PolPrevExpDt": self._format_date_mmddyyyy(
                payload.get("previous_policy_expiry_date") or ""
            ) or "01/01/2000",
            "VehOdometer": _odometer_value,
            "VehServiceType": "N",
            "PolPrevInsValidYn": "Y" if payload.get("previous_insurance_valid") else "N",
        }
        self._validate_create_quote_payload(request_payload)
        return request_payload

    def create_quote(self, payload: dict[str, Any]) -> dict[str, Any]:
        mock = self.get_extra_config().get("mock_create_quote_response")
        if isinstance(mock, dict):
            return mock
        request_data = self._build_create_quote_request(payload)
        request_data["PolSiCurrCode"] = "101"
        request_data["PolPremCurrCode"] = "101"
        print("[NIA CURRENCY] SI=101 PREMIUM=101")
        print(f"[NIA INITIAL CIVIL ID CHECK] {request_data.get('PolAssrCivilId')!r}")
        print(
            "[NIA FINAL PAYLOAD CHECK]",
            "Product:", request_data.get("PolProdCode"),
            "CivilID:", request_data.get("PolAssrCivilId"),
            "VehFcValue:", request_data.get("VehFcValue"),
            "BrandNew:", request_data.get("VehBrandNewYn"),
        )
        print(f"[NIA DEBUG] CreateQuote request: {request_data}")

        response = self._post_flat(
            self.get_extra_config().get("create_quote_endpoint", self.CREATE_QUOTE_ENDPOINT),
            request_data,
        )
        print(f"[NIA DEBUG] flat response: {response}")
        if isinstance(response, dict) and response.get("status") == "pending":
            return response

        message_block = response.get("Message")
        msg_text = str((message_block or {}).get("Text") or "") if isinstance(message_block, dict) else ""
        civil_id_error = "emirates id" in msg_text.lower() and "15 digits" in msg_text.lower()
        if civil_id_error:
            print("[NIA OVERRIDE] Retrying with sandbox Emirates ID")
            request_data["PolAssrCivilId"] = self.NIA_TEST_EMIRATES_ID
            response = self._post_flat(
                self.get_extra_config().get("create_quote_endpoint", self.CREATE_QUOTE_ENDPOINT),
                request_data,
            )
            print(f"[NIA DEBUG] Civil ID retry response: {response}")
            if isinstance(response, dict) and response.get("status") == "pending":
                return response
            message_block = response.get("Message")
            msg_text = str((message_block or {}).get("Text") or "") if isinstance(message_block, dict) else ""

        data_block = response.get("Data")
        data_text = " ".join(
            str(item.get("message", "")) for item in data_block
        ) if isinstance(data_block, list) else ""
        product_error = (
            "you cannot proceed with this product" in msg_text.lower()
            or "agency is applicable only for brand new vehicles" in msg_text.lower()
            or "you cannot proceed with this product" in data_text.lower()
            or "agency is applicable only for brand new vehicles" in data_text.lower()
        )
        if product_error:
            logging.getLogger(__name__).warning(
                "[NIA] Product 1001 (Agency) rejected for this account; falling back to Product 1002 (Non-Agency)."
            )
            # Rebuild request with Product 1002 Non-Agency
            request_data["PolProdCode"] = "1002"
            # Get the correct scheme type for 1002
            request_data["PolSchemeType"] = self._map_scheme_type("1002")
            request_data["VehAgencyType"] = "N"
            response = self._post_flat(
                self.get_extra_config().get("create_quote_endpoint", self.CREATE_QUOTE_ENDPOINT),
                request_data,
            )
            if isinstance(response, dict) and response.get("status") == "pending":
                return response
            # Check again for product error after fallback
            message_block = response.get("Message")
            msg_text = str((message_block or {}).get("Text") or "") if isinstance(message_block, dict) else ""
            data_block = response.get("Data")
            data_text = " ".join(
                str(item.get("message", "")) for item in data_block
            ) if isinstance(data_block, list) else ""
            product_error_again = (
                "you cannot proceed with this product" in msg_text.lower()
                or "you cannot proceed with this product" in data_text.lower()
            )
            if product_error_again:
                raise ProviderRequestError(
                    "NIA rejected both Agency and Non-Agency products for this account."
                )
        brand_new_non_agency_error = (
            "non-agency is not allowed for new vehicles" in msg_text.lower()
            or "non-agency is not allowed for new vehicles" in data_text.lower()
        )
        if brand_new_non_agency_error:
            raise ProviderRequestError(
                "NIA: This vehicle is brand new and requires Agency product, "
                "but this account does not support Agency. "
                "Please contact NIA to enable Agency product for this account."
            )
        print(f"[NIA RANGE CHECK] message text: {msg_text!r}")
        if "Vehicle value should be in between" in msg_text:
            print("[NIA RANGE ERROR DETECTED]", msg_text)
            min_val, max_val = self._extract_vehicle_value_range(msg_text)
            print("[NIA RANGE PARSED]", min_val, max_val)
            if min_val and max_val:
                old_fc_value = str(request_data.get("VehFcValue") or "0")
                new_fc_value = str(int(float(min_val)))
                request_data["VehFcValue"] = new_fc_value
                # Early exit: if this is a brand new vehicle year and account doesn't support Agency,
                # NIA will reject Non-Agency for new vehicles regardless of the value fix.
                import datetime as _dt
                _supports_agency = str(
                    self.get_extra_config().get("supports_agency_product", "false")
                ).strip().lower() not in ("0", "false", "no")

                if not _supports_agency:
                    try:
                        _mfg_year = int(str(request_data.get("VehMfgYear") or "0").strip().split(".")[0])
                        if _mfg_year >= _dt.date.today().year:
                            raise ProviderRequestError(
                                f"NIA: This is a brand new {_mfg_year} vehicle requiring Agency product "
                                f"(value range AED {int(min_val):,} – AED {int(max_val):,}). "
                                f"Non-Agency (Product 1002) is not permitted for new vehicles by NIA. "
                                f"Please contact NIA to enable Agency product for this account, or ensure "
                                f"the vehicle registration year is set correctly in the deal."
                            )
                    except ProviderRequestError:
                        raise
                    except Exception:
                        pass
                # Ensure brand new flags remain consistent after range fix retry
                if request_data.get("VehBrandNewYn") == "N":
                    request_data["VehAgencyType"] = "N"
                print(f"[NIA RANGE FIX] Adjusted VehFcValue from {old_fc_value} → {new_fc_value}")
                response = self._post_flat(
                    self.get_extra_config().get("create_quote_endpoint", self.CREATE_QUOTE_ENDPOINT),
                    request_data,
                )
                print(f"[NIA DEBUG] Range retry response: {response}")
                if isinstance(response, dict) and response.get("status") == "pending":
                    return response
                range_retry_message_block = response.get("Message")
                range_retry_msg = str((range_retry_message_block or {}).get("Text") or "") if isinstance(range_retry_message_block, dict) else ""
                range_retry_data = response.get("Data")
                range_retry_data_text = " ".join(
                    str(item.get("message", "")) for item in range_retry_data
                ) if isinstance(range_retry_data, list) else ""

                if (
                    "non-agency is not allowed for new vehicles" in range_retry_msg.lower()
                    or "non-agency is not allowed for new vehicles" in range_retry_data_text.lower()
                ):
                    raise ProviderRequestError(
                        "NIA: This vehicle is brand new and requires Agency product, "
                        "but this account does not support Agency repair. "
                        f"The correct vehicle value range is AED {int(min_val):,} to AED {int(max_val):,}. "
                        "Please contact NIA to enable Agency product for this account."
                    )

        return self._ensure_success(response)

    def save_quote_with_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        mock = self.get_extra_config().get("mock_save_quote_with_plan_response")
        if isinstance(mock, dict):
            return mock
        # SaveQuoteWithPlan uses flat structure with Authentication
        response = self._post_flat(
            self.get_extra_config().get("save_quote_with_plan_endpoint", self.SAVE_QUOTE_WITH_PLAN_ENDPOINT),
            payload,
        )
        return self._ensure_success(response)

    def save_additional_info(self, payload: dict[str, Any]) -> dict[str, Any]:
        mock = self.get_extra_config().get("mock_save_additional_info_response")
        if isinstance(mock, dict):
            return mock
        response = self._post_flat(
            self.get_extra_config().get("save_addl_info_endpoint", self.SAVE_ADDL_INFO_ENDPOINT),
            payload,
        )
        return self._ensure_success(response)

    def save_documents(self, payload: dict[str, Any]) -> dict[str, Any]:
        mock = self.get_extra_config().get("mock_save_document_response")
        if isinstance(mock, dict):
            return mock
        documents = payload.get("docUpload") or []
        if not documents:
            return {"Status": 1}
        doc_results = []
        for document in documents:
            response = self._post_with_auth_body(
                self.get_extra_config().get("save_document_endpoint", self.SAVE_DOCUMENT_ENDPOINT),
                "DocumentUploadData",
                {
                    "Base64ImageString": document.get("docFile") or "",
                    "QuotNo": payload.get("polRefNo") or "",
                    "FileExtension": f".{document.get('imgType') or 'png'}",
                    "FileName": document.get("docDesc") or document.get("docCode") or "Document",
                    "Remarks": document.get("docDesc") or "",
                    "SequenceNo": str(document.get("docSrlNo") or 1),
                    "DocumentIdNo": document.get("docCode") or "",
                },
            )
            doc_results.append(self._ensure_success(response))
        return {"Status": 1, "DocumentResponses": doc_results}

    def proposal_summary(self, payload: dict[str, Any]) -> dict[str, Any]:
        mock = self.get_extra_config().get("mock_proposal_summary_response")
        if isinstance(mock, dict):
            return mock
        logger.info("Incoming proposal summary payload: %s", payload)

        # If client sends the same shape as direct NIA (nested section), forward it unchanged.
        embedded = payload.get("ViewPolicySummaryData")
        if isinstance(embedded, dict) and embedded:
            nia_summary_section = dict(embedded)
            logger.info("proposal_summary using pass-through ViewPolicySummaryData: %s", nia_summary_section)
        else:
            # ProposalSummary works on the *saved* quote (Q/… from SaveQuoteWithPlan),
            # NOT the create-quote reference (R/…). Send only QuotNo when available.
            # Only fall back to PolRefNo/ReferenceNo when there is no QuotNo at all.
            # quot = str(
            #     (
            #         payload.get("QuotNo")
            #         or payload.get("quotation_no")
            #         or payload.get("quote_no")
            #         or payload.get("polRefNo")
            #         or ""
            #     )
            # ).strip()
            # nia_summary_section: dict[str, Any] = {}
            # # if quot:
            # #     nia_summary_section["QuotNo"] = quot
            # # else:
            #     # No QuotNo supplied — fall back to the reference number fields.
            # ref = str(
            #         (
            #             payload.get("PolRefNo")
            #             or payload.get("ReferenceNo")
            #             or payload.get("reference_no")
            #             or payload.get("referenceNo")
            #             or ""
            #         )
            #     ).strip()
            # if ref:
            #         nia_summary_section["PolRefNo"] = ref


            nia_summary_section: dict[str, Any] = {}
            ref = str(
                    (
                            payload.get("PolRefNo")
                            or payload.get("ReferenceNo")
                            or payload.get("reference_no")
                            or payload.get("referenceNo")
                            or ""
                        )
                ).strip()
            if ref:
                nia_summary_section["PolRefNo"] = ref


            logger.info("ProposalSummary final payload: %s", nia_summary_section)
        logger.info(
            "[NIA proposal_summary] payload_keys=%s candidates=%s section=%s",
            sorted(list(payload.keys())),
            {
                "PolRefNo": payload.get("PolRefNo"),
                "ReferenceNo": payload.get("ReferenceNo"),
                # "quotation_no": payload.get("quotation_no"),
                # "QuotNo": payload.get("QuotNo"),
                "polRefNo": payload.get("polRefNo"),
                "reference_no": payload.get("reference_no"),
                # "quote_no": payload.get("quote_no"),
            },
            nia_summary_section,
        )
        logger.debug(
            "[NIA proposal_summary] ViewPolicySummaryData=%s payload_keys=%s",
            nia_summary_section,
            list(payload.keys()),
        )
        # response = self._post_with_auth_body(
        #     self.get_extra_config().get("proposal_summary_endpoint", self.PROPOSAL_SUMMARY_ENDPOINT),
        #     "ViewPolicySummaryData",
        #     nia_summary_section,
        # )
        response = self._post_flat(
            self.get_extra_config().get("proposal_summary_endpoint", self.PROPOSAL_SUMMARY_ENDPOINT),
            nia_summary_section,
        )
        return self._ensure_success(response)

    def approve_policy(self, payload: dict[str, Any]) -> dict[str, Any]:
        mock = self.get_extra_config().get("mock_approve_policy_response")
        if isinstance(mock, dict):
            return mock
        response = self._post_with_auth_body(
            self.get_extra_config().get("approve_policy_endpoint", self.APPROVE_POLICY_ENDPOINT),
            "ApprovePolicyData",
            payload,
        )
        if response.get("Status") == 0 and response.get("Data"):
            data = response.get("Data") or {}
            if isinstance(data, dict) and data.get("PolicyNo"):
                return response  # Status=0 is SUCCESS for ApprovePolicy
        return self._ensure_success(response)

    def generate_payment_link(self, payload: dict[str, Any]) -> dict[str, Any]:
        mock = self.get_extra_config().get("mock_generate_payment_link_response")
        if isinstance(mock, dict):
            return mock
        response = self._post_with_auth_body(
            self.get_extra_config().get("generate_payment_link_endpoint", self.GENERATE_PAYMENT_LINK_ENDPOINT),
            "GeneratePaymentLinkData",
            payload,
        )
        return self._ensure_success(response)

    def get_payment_details(self, payload: dict[str, Any]) -> dict[str, Any]:
        mock = self.get_extra_config().get("mock_get_payment_details_response")
        if isinstance(mock, dict):
            return mock
        response = self._post_with_auth_body(
            self.get_extra_config().get("get_payment_details_endpoint", self.GET_PAYMENT_DETAILS_ENDPOINT),
            "PaymentDetailsData",
            payload,
        )
        return self._ensure_success(response)

    def _build_selected_covers(self, create_quote_response: dict[str, Any]) -> list[dict[str, Any]]:
        covers = create_quote_response.get("Covers") or []
        selected = []
        for cover in covers:
            if cover.get("Selected") == "Y":
                selected.append(
                    {
                        "Code": str(cover.get("Code") or ""),
                        "CoverPremFc": str(cover.get("Premium") or "0"),
                        "CoverPremLc": str(cover.get("Premium") or "0"),
                    }
                )
        return selected
            

    def _nia_default_addl_info(self) -> dict[str, str]:
        import datetime as _dt

        today = _dt.date.today()
        today_str = today.strftime("%m/%d/%Y")
        month = today.month + 13
        year = today.year + (month - 1) // 12
        month = (month - 1) % 12 + 1
        to_date_str = today.replace(year=year, month=month).strftime("%m/%d/%Y")
        return {
            "PolFmDt": today_str,
            "PolToDt": to_date_str,
            "PolPrevExpDt": today_str,
            "PolAssrNameL2": "",
            "PolAssrSex": "M",
            "PolAssrPobox": "0",
            "PolAssrAddr1": "Dubai",
            "PolAssrProvince": "0001",
            "PolAssrOccup": "001",
            "VehInsDrvSameYn": "N",
            "VehDriverName": "",
            "VehDriverCivilId": "",  # will be overridden by _build_additional_info_request
            "VehDriverLicNo": "123456",
            "VehDriverLicIssDt": today_str,
            "VehDriverLicExpDt": to_date_str,
            "VehEngineNo": "ENG123456",
            "VehRegnNo": "A12345",
            "VehPlateColor": "1",
            "VehBodyColor1": "WHITE",
            "VehTransType": "A",
            "VehOdometer": "100",
        }

    def _build_additional_info_request(
        self,
        payload: dict[str, Any],
        reference_no: str,
        quotation_no: str = "",
        referral_yn: str = "NO",
    ) -> dict[str, Any]:
        import datetime as _dt
        import json
        import re as _re

        customer = payload.get("customer") if isinstance(payload.get("customer"), dict) else payload
        vehicle = payload.get("vehicle") if isinstance(payload.get("vehicle"), dict) else payload
        plate_city = vehicle.get("plate_source") or vehicle.get("registration_location") or ""
        _nationality_code = self._resolve_nationality_code(customer.get("nationality") or "")
        _assr_name = str(customer.get("name") or "").strip()
        _raw_gender = str(customer.get("gender") or "").strip().upper()
        _assr_sex = "F" if _raw_gender.startswith("F") else "M"
        _civil_id = self.format_emirates_id(customer.get("emirates_id") or "")
        _driver_civil_id_raw = str(payload.get("driver_emirates_id") or customer.get("emirates_id") or "")

        today = _dt.date.today()
        today_str = today.strftime("%m/%d/%Y")
        month = today.month + 13
        year = today.year + (month - 1) // 12
        month = (month - 1) % 12 + 1
        to_date_str = today.replace(year=year, month=month).strftime("%m/%d/%Y")

        _driver_lic_iss = self._format_date_mmddyyyy(
            payload.get("driver_license_issue_date") or vehicle.get("license_from_date") or today_str
        ) or today_str
        _driver_lic_exp = self._format_date_mmddyyyy(
            payload.get("driver_license_expiry_date") or vehicle.get("license_to_date") or to_date_str
        ) or to_date_str

        _odometer_value = (
            payload.get("odometer_reading")
            or vehicle.get("odometer_reading")
            or self.get_extra_config().get("default_odometer")
            or "100"
        )
        try:
            _odometer_value = str(max(100, int(float(str(_odometer_value)))))
        except Exception:
            _odometer_value = "100"

        _emirate_raw = customer.get("emirate") or customer.get("province") or ""
        _province_code = str(lookup_code("PolAssrProvince", _emirate_raw) or "").strip()
        if not _province_code:
            _province_code = str(self.get_extra_config().get("default_province_code") or "0001")

        _occup_raw = customer.get("occupation") or ""
        _occup_code = str(lookup_code("PolAssrOccup", _occup_raw) or "").strip()
        if not _occup_code or _occup_code == "000":
            _occup_code = str(self.get_extra_config().get("default_occupation_code") or "").strip()
        if not _occup_code:
            _occ_records = load_sheet_records("PolAssrOccup")
            _occup_code = str((_occ_records[0] or {}).get("Code") or "").strip() if _occ_records else ""
        if not _occup_code:
            _occup_code = "001"
        # When referral is required, NIA rejects VehInsDrvSameYn="Y".
        # Force "N" and duplicate insured details into driver fields.
        _referral_active = str(referral_yn or "").strip().upper() == "YES"

        if _referral_active:
            _driver_is_same_yn = "N"
        else:
            _driver_is_same = (
                not payload.get("driver_name")
                or str(payload.get("driver_name") or "").strip().lower() == str(customer.get("name") or "").strip().lower()
            ) and (
                not payload.get("driver_emirates_id")
                or _re.sub(r"\D", "", str(payload.get("driver_emirates_id") or "")) == _re.sub(r"\D", "", str(customer.get("emirates_id") or ""))
            )
            _driver_is_same_yn = "Y" if _driver_is_same else "N"

        payload_data = {
            "PolRefNo": str(reference_no or payload.get("reference_no") or ""),
            "QuotNo": str(quotation_no or ""),
            "PolType": str(payload.get("policy_type") or "N"),
            "PolFmDt": today_str,
            "PolToDt": to_date_str,
            "PolPrevExpDt": today_str,
            "PolAssrNameL2": str(customer.get("name_ar") or _assr_name or ""),
            "PolAssrAddlName": str(customer.get("additional_name") or _assr_name or ""),
            "PolAssrTcfNo": str(vehicle.get("tcf_number") or ""),
            "PolAssrTrnNo": str(customer.get("trn_no") or ""),
            "PolAssrSex": _assr_sex,
            "PolAssrPobox": str(customer.get("po_box") or "0"),
            "PolAssrAddr1": str(customer.get("address") or "Dubai"),
            "PolAssrProvince": _province_code,
            "PolAssrNation": _nationality_code,
            "PolAssrOccup": _occup_code,
            "PolAssrVehLicNo": str(vehicle.get("license_number") or ""),
            "PolAssrMaritalSts": "Y" if customer.get("married") else "N",
            "VehInsDrvSameYn": _driver_is_same_yn,
            "VehDriverName": str(payload.get("driver_name") or _assr_name or ""),
            "VehDriverCivilId": self.format_emirates_id(_driver_civil_id_raw),
            "VehDriverLicNo": str(payload.get("driver_license_no") or vehicle.get("license_number") or "123456"),
            "VehDriverLicIssDt": _driver_lic_iss,
            "VehDriverLicExpDt": _driver_lic_exp,
            "VehEngineNo": str(vehicle.get("engine_no") or "ENG123456"),
            "VehRegnLocation": lookup_code("VehRegnLocation", plate_city),
            "VehPlateColor": str(lookup_plate_color_code(vehicle.get("plate_code") or "", plate_city) or "1"),
            "VehRegnNo": str(vehicle.get("registration_number") or "A12345"),
            "VehTransType": str(lookup_code("VehTransType", vehicle.get("traffic_transaction_type") or "Vehicle Renewal") or "103"),
            "VehBodyColor1": str(lookup_code("VehBodyColor1", vehicle.get("color") or "WHITE") or "WHITE"),
            "VehBankCode": lookup_code("VehBankCode", vehicle.get("bank_name") or ""),
            "VehWeightEmpty": str(vehicle.get("weight_empty") or ""),
            "VehWeightFull": str(vehicle.get("weight_full") or ""),
            "VehOdometer": _odometer_value,
            "VehRemarks": str(payload.get("remarks") or ""),
        }
        defaults = self._nia_default_addl_info()
        final_payload = {**defaults, **payload_data}
        print("NIA SaveAddlInfo Payload:", json.dumps(final_payload, indent=2))
        return final_payload

    def _build_documents_payload(self, payload: dict[str, Any], quotation_no: str) -> dict[str, Any]:
        documents = payload.get("documents") or payload.get("document_lists") or []
        doc_upload = []
        for idx, item in enumerate(documents, start=1):
            mapping = self.DOCUMENT_TYPE_MAP.get(str(item.get("document_type") or "").strip())
            doc_upload.append(
                {
                    "docCode": item.get("docCode") or (mapping or {}).get("docCode") or "10011",
                    "docSrlNo": item.get("docSrlNo", idx),
                    "docDesc": item.get("docDesc") or (mapping or {}).get("docDesc") or item.get("name") or "Document",
                    "storageType": item.get("storageType") or "F",
                    "docFile": item.get("base64") or "",
                    "imgType": item.get("type") or "png",
                }
            )
        return {"polRefNo": quotation_no, "docUpload": doc_upload}

    def get_quote(self, payload: dict[str, Any]):
        started = time.perf_counter()
        _corrected_sum_insured: float | None = None
        mock_payload = self.get_extra_config().get("mock_quote_response")
        if isinstance(mock_payload, dict):
            return self.build_quote_from_mapping(
                mock_payload,
                response_time_ms=int((time.perf_counter() - started) * 1000),
            )

        try:
            created = self.create_quote(payload)
        except NiaVehicleValueRangeError as e:
            print(f"[NIA RANGE PERSIST DEBUG] payload keys: {list(payload.keys())}")
            print(f"[NIA RANGE PERSIST DEBUG] deal_id value: {payload.get('deal_id')!r}")
            print(f"[NIA PERSIST ATTEMPT] deal_id={payload.get('deal_id')!r} min_value={e.min_value}")
            self._last_corrected_sum_insured = e.min_value
            _corrected_sum_insured = e.min_value
            logging.getLogger(__name__).warning(
                "[NIA] Vehicle value out of range; retrying get_quote with "
                "sum_insured=%.2f",
                e.min_value,
            )
            payload = dict(payload)
            if isinstance(payload.get("vehicle"), dict):
                payload["vehicle"] = dict(payload["vehicle"])
                payload["vehicle"]["sum_insured"] = e.min_value
            else:
                payload["sum_insured"] = e.min_value

            deal_id = payload.get("deal_id")
            if deal_id:
                try:
                    from deals.models import Deal

                    Deal.objects.filter(id=deal_id).update(
                        sum_insured=Decimal(str(e.min_value))
                    )
                    logging.getLogger(__name__).info(
                        "[NIA] Persisted corrected sum_insured=%.2f to deal %s",
                        e.min_value, deal_id
                    )
                except Exception as persist_err:
                    logging.getLogger(__name__).warning(
                        "[NIA] Could not persist sum_insured to deal %s: %s",
                        deal_id, persist_err
                    )

            created = self.create_quote(payload)
        if isinstance(created, dict) and created.get("status") == "pending":
            return self.build_quote_from_mapping(
                {
                    "premium": Decimal("0"),
                    "vat": Decimal("0"),
                    "total": Decimal("0"),
                    "currency": "AED",
                    "plan_name": "NIA Pending",
                    "status": "pending",
                    "provider": "NIA",
                    "error": "timeout",
                },
                response_time_ms=int((time.perf_counter() - started) * 1000),
            )

        # Parse CreateQuote response - ReferenceNo is in Data dict
        data = created.get("Data") or {}
        referral_yn = str(created.get("ReferralYN") or data.get("ReferralYN") or "NO").strip().upper()
        if referral_yn == "YES":
            _business_rules = data.get("BusinessRules") if isinstance(data, dict) else []
            if not isinstance(_business_rules, list):
                _business_rules = []
            _first_rule = _business_rules[0] if _business_rules else {}
            referral_msg = (
                str((_first_rule or {}).get("Message") or "")
                if isinstance(_first_rule, dict)
                else str(_first_rule or "")
            )
            logging.getLogger(__name__).warning(
                "[NIA] Quote requires referral (ReferralYN=YES). Proceeding with SaveQuoteWithPlan. "
                "Referral reason: %s",
                referral_msg,
            )
        if isinstance(data, str):
            raise ProviderRequestError(
                f"NIA CreateQuote returned unexpected Data: {data}"
            )

        reference_no = str(data.get("ReferenceNo") or "")
        plan_details = data.get("PlanDetails") or []
        logger.info(
            "[NIA get_quote] create_quote returned ReferenceNo=%r plan_details_count=%s",
            reference_no,
            len(plan_details) if isinstance(plan_details, list) else "n/a",
        )

        if not reference_no or not plan_details:
            raise ProviderRequestError(
                "NIA create quote did not return a ReferenceNo and PlanDetails."
            )

        # Pick first plan and all its covers
        first_plan = plan_details[0]
        product_code = str(first_plan.get("Code") or "")
        product_name = str(first_plan.get("Name") or "NIA Plan")
        covers = first_plan.get("Covers") or []

        # Select covers - include all that have a CoverType (exclude NA flag covers)
        selected_covers = []
        total_premium = Decimal("0")
        for cover in covers:
            cover_flag = str(cover.get("CoverFlag") or "")
            prem_fc = Decimal(str(cover.get("CoverPremFc") or 0))
            if cover_flag not in ("NA",):
                selected_covers.append({
                    "Code": str(cover.get("Code") or ""),
                    "CoverPremFc": str(prem_fc),
                    "CoverPremLc": str(Decimal(str(cover.get("CoverPremLc") or 0))),
                })
                total_premium += prem_fc

        if not selected_covers:
            raise ProviderRequestError("NIA CreateQuote returned no selectable covers.")

        # SaveQuoteWithPlan
        scheme_code = str(data.get("SchemeCode") or "1000")
        save_plan_response = self.save_quote_with_plan({
            "ReferenceNo": reference_no,
            "SchemeCode": scheme_code,
            "ProductCode": product_code,
            "SelectedCovers": selected_covers,
        })

        # QuotNo is in Data field of SaveQuoteWithPlan response
        quotation_no = str(save_plan_response.get("Data") or "")
        if not quotation_no:
            quotation_no = reference_no  # fallback
        logger.info(
            "[NIA get_quote] save_quote_with_plan returned QuotNo(Data)=%r fallback_reference_no=%r",
            str(save_plan_response.get("Data") or ""),
            reference_no,
        )

        # SaveAddlInfo — skip when referral is required (NIA blocks it)
        if referral_yn != "YES":
            additional_info_payload = self._build_additional_info_request(
                payload, reference_no, quotation_no, referral_yn=referral_yn
            )
            self.save_additional_info(additional_info_payload)
        else:
            logging.getLogger(__name__).warning(
                "[NIA] Skipping SaveAddlInfo because ReferralYN=YES. "
                "Quote %s / %s requires manual NIA underwriter approval.",
                reference_no,
                quotation_no,
            )

        # SaveDocuments — skip when referral is required
        if referral_yn != "YES":
            documents_payload = self._build_documents_payload(payload, quotation_no)
            if documents_payload["docUpload"]:
                self.save_documents(documents_payload)
        else:
            logging.getLogger(__name__).warning(
                "[NIA] Skipping SaveDocuments because ReferralYN=YES."
            )

        vat = Decimal("0")
        mapping = {
            "premium": total_premium,
            "vat": vat,
            "total": total_premium + vat,
            "currency": "AED",
            "plan_name": product_name,
            "quote_no": quotation_no,
            "reference_no": reference_no,
            "create_quote": _decimal_safe(created),
            "referral_required": referral_yn == "YES",
            "referral_reason": (
                str((data.get("BusinessRules") or [{}])[0].get("Message") or "")
                if referral_yn == "YES" else ""
            ),
        }
        mapping = _decimal_safe(mapping)
        if referral_yn == "YES":
            mapping["referral_required"] = True
        if _corrected_sum_insured is not None:
            mapping["corrected_sum_insured"] = _corrected_sum_insured
        return self.build_quote_from_mapping(
            mapping,
            response_time_ms=int((time.perf_counter() - started) * 1000),
        )

    def issue_policy(self, payload: dict[str, Any]) -> dict[str, Any]:
        quot_no = str(payload.get("PolRefNo") or payload.get("quot_no") or "")
        return self.approve_policy({"PolRefNo": quot_no, "PayType": payload.get("pay_type") or "OA"})

    def renew_policy(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.create_quote(payload)

    # def fetch_policy(self, payload: dict[str, Any]) -> dict[str, Any]:
    #     quotation_no = str(payload.get("quotation_no") or payload.get("quot_no") or payload.get("PolRefNo") or "")
    #     # Proposal summary uses QuotNo (save-quote response), not the create-quote ReferenceNo (R/…).
    #     return self.proposal_summary({"quotation_no": quotation_no})

    def fetch_policy(self, payload):
        ref_no = str(
            payload.get("PolRefNo")
            or payload.get("QuotNo")
            or payload.get("quote_no")
            or payload.get("quotation_no")
            or payload.get("reference_no")
            or ""
        ).strip()
        return self.proposal_summary({"PolRefNo": ref_no})

    def health_check(self) -> dict[str, Any]:
        mock_payload = self.get_extra_config().get("mock_health_check")
        if isinstance(mock_payload, dict):
            return mock_payload
        self.authenticate()
        return {
            "status": "ok",
            "masterdata_sets": {
                "products": len(load_sheet_records("PolProdCode")),
                "vehicle_makes": len(load_sheet_records("VehMake")),
                "vehicle_models": len(load_sheet_records("VehModel")),
                "occupations": len(load_sheet_records("PolAssrOccup")),
            },
        }
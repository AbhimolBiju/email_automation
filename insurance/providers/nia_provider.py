from __future__ import annotations

import time
from decimal import Decimal
from typing import Any
from datetime import datetime
from .base import BaseInsuranceProvider
from .exceptions import ProviderAuthenticationError, ProviderRequestError
from .nia_masterdata import (
    load_sheet_records,
    lookup_code,
    lookup_description,
    lookup_plate_color_code,
)


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
        self._token: str | None = None

    def _ensure_success(self, payload: dict[str, Any]) -> dict[str, Any]:
        status_value = payload.get("Status")
        if isinstance(status_value, list):
            status_block = status_value[0] if status_value else {}
        elif isinstance(status_value, dict):
            status_block = status_value
        else:
            status_block = {"Code": "", "Description": ""}

        code = str(status_block.get("Code", "")).strip()
        if code and not code.startswith(("1", "2", "3")):
            raise ProviderRequestError(str(status_block.get("Description") or f"NIA request failed with status code {code}."))
        if payload.get("Status") == 0:
            raise ProviderRequestError(str(payload.get("StatusMessage") or "NIA request failed."))
        return payload

    def authenticate(self) -> str | None:
        if self._token:
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
        )
        self._ensure_success(response)
        token = response.get("Data")
        if isinstance(token, list):
            token = (token[0] or {}).get("Token")
        if not token:
            raise ProviderAuthenticationError("NIA login did not return a token.")
        self._token = str(token)
        return self._token

    def get_auth_headers(self) -> dict[str, str]:
        if self.get_extra_config().get("use_authorization_header", False):
            token = self.authenticate()
            template = str(
                self.get_extra_config().get(
                    "authorization_header_template",
                    "{token}",
                )
            )
            return {"Authorization": template.format(token=token)}
        return {}
    
    from typing import Any

    def _format_date(self, value: Any) -> str:
        text = str(value).strip() if value not in (None, "") else ""
        if not text:
            return ""
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(text, fmt).strftime("%d/%m/%Y")
            except ValueError:
                continue
        raise ValueError(f"Invalid date format: {value}")

    def _user_id(self) -> str:
        user_id = self.get_extra_config().get("user_id") or self.resolve_config_value("username", "")
        return str(user_id)

    def _request_payload(self, section_name: str, section_value: Any) -> dict[str, Any]:
        return {
            "Authentication": {"Token": self.authenticate(), "UserId": self._user_id()},
            section_name: section_value,
        }

    def _post_with_auth_body(self, path: str, section_name: str, section_value: Any) -> dict[str, Any]:
        return self._request(
            method="POST",
            path=path,
            json_payload=self._request_payload(section_name, section_value),
            authenticated=False,
        )

    def _map_product_code(self, insurance_type: str | None, agency_repair: bool) -> str:
        if insurance_type == "third_party":
            return lookup_code("PolProdCode", "Third Party Liability")
        return lookup_code(
            "PolProdCode",
            "Motor Comprehensive – Agency" if agency_repair else "Motor Comprehensive –Non Agency",
        )

    def _map_scheme_type(self, product_code: str) -> str:
        for record in load_sheet_records("PolSchemeType"):
            if record.get("Product Code") == str(product_code):
                return record.get("Code", "")
        return ""

    def _build_create_quote_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        customer = payload.get("customer") if isinstance(payload.get("customer"), dict) else payload
        vehicle = payload.get("vehicle") if isinstance(payload.get("vehicle"), dict) else payload
        product_code = self._map_product_code(payload.get("sub_type"), bool(vehicle.get("agency_repair")))
        return {
            "PolBchCode": str(self.get_extra_config().get("business_channel_code", "101")),
            "PolPrtnrCode": str(self.get_extra_config().get("partner_code", "201001")),
            "PolDeptCode": str(self.get_extra_config().get("department_code", "10")),
            "PolPartyCode": str(self.get_extra_config().get("party_code", "201001")),
            "PolDivnCode": str(self.get_extra_config().get("division_code", "813")),
            "PolAssrCode": str(self.get_extra_config().get("assured_code", "")),
            "PolAssrName": str(customer.get("name") or ""),
            "PolAssrLastName": str(customer.get("last_name") or ""),
            "PolAssrType": lookup_code("PolAssrType", customer.get("assured_type") or "INDIVIDUAL"),
            "PolAssrDob": self._format_date(customer.get("date_of_birth")),
            "PolAssrAge": int(customer.get("insured_age") or payload.get("insured_age") or 0),
            "PolAssrCivilId": str(customer.get("emirates_id") or ""),
            "TradeLicNo": str(customer.get("trade_license_no") or ""),
            "PolAssrEmail": str(customer.get("email") or ""),
            "PolAssrMobile": str(customer.get("mobile_number") or ""),
            "PolAssrPhone": str(customer.get("phone_number") or ""),
            "PolProdCode": product_code,
            "PolSchemeType": self._map_scheme_type(product_code),
            "VehChassisNo": str(vehicle.get("chassis_number") or ""),
            "VehUsage": lookup_code("VehUsage", vehicle.get("vehicle_usage") or "PRIVATE (Indiv./Comm.)"),
            "VehMake": lookup_code("VehMake", vehicle.get("make_id") or ""),
            "VehModel": lookup_code("VehModel", vehicle.get("model_id") or "", code_key="MODEL CODE", description_key="MODE DESCRIPTION"),
            "VehBodyType": lookup_code("VehBodyType", vehicle.get("body_type_id") or ""),
            "VehNoCylinder": lookup_code("VehNoCylinder", vehicle.get("engine_capacity_id") or "4 CYLINDERS"),
            "VehNoSeats": lookup_code("VehNoSeats", vehicle.get("seating_capacity") or "5"),
            "VehNoDoors": lookup_code("VehNoDoors", vehicle.get("door_count") or "5 Doors"),
            "VehCc": lookup_code("VehCc", vehicle.get("engine_capacity") or ""),
            "VehMfgYear": str(vehicle.get("model_year") or ""),
            "VehBrandNew": "Y" if vehicle.get("is_vehicle_brand_new") else "N",
            "VehAgencyRep1Yn": lookup_code("VehAgencyType", "Agency" if vehicle.get("agency_repair") else "Non Agency"),
            "VehFcValue": str(vehicle.get("sum_insured") or payload.get("sum_insured") or "0"),
            "VehLoadCapacity": lookup_code("VehLoadCapacity", vehicle.get("load_capacity") or "No Loading"),
            "VehRegion": lookup_description("VehRegion", "GCC" if vehicle.get("is_gcc_spec") else "Non-GCC"),
           "VehRegnDt": self._format_date(vehicle.get("registration_date")),
            "VehAge": int(payload.get("vehicle_age") or 0),
            "VehPrevInsType": lookup_code("VehPrevInsType", payload.get("previous_insurance_type") or 1),
            "VehAccident": lookup_code("VehAccident", "Yes" if payload.get("total_loss") else "No"),
            "VehRegnCardExp": lookup_code("VehRegnCardExp", "Yes" if payload.get("registration_card_expired") else "No"),
            "VehOffroadYn": lookup_code("VehOffroadYn", "Yes" if vehicle.get("offroad_cover") else "No"),
            "PolPrevExpDt": self._format_date(payload.get("previous_policy_expiry_date")),
            "VehTransType": lookup_code("VehTransType", vehicle.get("traffic_transaction_type") or "Vehicle Renewal"),
            "VehPrevClaimHisYn": "Y" if payload.get("previous_claim_history") else "N",
        }

    def create_quote(self, payload: dict[str, Any]) -> dict[str, Any]:
        mock = self.get_extra_config().get("mock_create_quote_response")
        if isinstance(mock, dict):
            return mock
        response = self._post_with_auth_body(
            self.get_extra_config().get("create_quote_endpoint", self.CREATE_QUOTE_ENDPOINT),
            "Data",
            self._build_create_quote_request(payload),
        )
        return self._ensure_success(response)

    def save_quote_with_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        mock = self.get_extra_config().get("mock_save_quote_with_plan_response")
        if isinstance(mock, dict):
            return mock
        response = self._post_with_auth_body(
            self.get_extra_config().get("save_quote_with_plan_endpoint", self.SAVE_QUOTE_WITH_PLAN_ENDPOINT),
            "SelectedCoverData",
            [payload],
        )
        return self._ensure_success(response)

    def save_additional_info(self, payload: dict[str, Any]) -> dict[str, Any]:
        mock = self.get_extra_config().get("mock_save_additional_info_response")
        if isinstance(mock, dict):
            return mock
        response = self._post_with_auth_body(
            self.get_extra_config().get("save_addl_info_endpoint", self.SAVE_ADDL_INFO_ENDPOINT),
            "AdditionalDetailsData",
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
        return self._ensure_success(response)

    def proposal_summary(self, payload: dict[str, Any]) -> dict[str, Any]:
        mock = self.get_extra_config().get("mock_proposal_summary_response")
        if isinstance(mock, dict):
            return mock
        response = self._post_with_auth_body(
            self.get_extra_config().get("proposal_summary_endpoint", self.PROPOSAL_SUMMARY_ENDPOINT),
            "ViewPolicySummaryData",
            {"QuotNo": payload.get("PolRefNo") or payload.get("quotation_no") or payload.get("QuotNo") or ""},
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

    def _build_additional_info_request(self, payload: dict[str, Any], quotation_no: str) -> dict[str, Any]:
        customer = payload.get("customer") if isinstance(payload.get("customer"), dict) else payload
        vehicle = payload.get("vehicle") if isinstance(payload.get("vehicle"), dict) else payload
        plate_city = vehicle.get("plate_source") or vehicle.get("registration_location") or ""
        return {
            "PolRefNo": str(payload.get("reference_no") or ""),
            "PolType": str(payload.get("policy_type") or "N"),
            "PolFmDt": str(payload.get("policy_from_date") or ""),
            "PolToDt": str(payload.get("policy_to_date") or ""),
            "PolAssrNameL2": str(customer.get("name_ar") or ""),
            "PolAssrAddlName": str(customer.get("additional_name") or customer.get("name") or ""),
            "PolAssrTcfNo": str(vehicle.get("tcf_number") or ""),
            "PolAssrTrnNo": str(customer.get("trn_no") or ""),
            "PolAssrSex": lookup_code("PolAssrSex", customer.get("gender") or ""),
            "PolAssrPobox": str(customer.get("po_box") or ""),
            "PolAssrAddr1": str(customer.get("address") or ""),
            "PolAssrProvince": lookup_code("PolAssrProvince", customer.get("emirate") or ""),
            "PolAssrNation": lookup_code("PolAssrNation", customer.get("nationality") or ""),
            "PolAssrOccup": lookup_code("PolAssrOccup", customer.get("occupation") or ""),
            "PolAssrVehLicNo": str(vehicle.get("license_number") or ""),
            "PolAssrMaritalSts": "Y" if customer.get("married") else "N",
            "VehDriverName": str(payload.get("driver_name") or customer.get("name") or ""),
            "VehDriverCivilId": str(payload.get("driver_emirates_id") or customer.get("emirates_id") or ""),
            "VehDriverLicNo": str(payload.get("driver_license_no") or vehicle.get("license_number") or ""),
            "VehDriverLicIssDt": str(payload.get("driver_license_issue_date") or vehicle.get("license_from_date") or ""),
            "VehDriverLicExpDt": str(payload.get("driver_license_expiry_date") or vehicle.get("license_to_date") or ""),
            "VehEngineNo": str(vehicle.get("engine_no") or ""),
            "VehRegnLocation": lookup_code("VehRegnLocation", plate_city),
            "VehPlateColor": lookup_plate_color_code(vehicle.get("plate_code") or "", plate_city),
            "VehRegnNo": str(vehicle.get("registration_number") or ""),
            "VehTransType": lookup_code("VehTransType", vehicle.get("traffic_transaction_type") or ""),
            "VehBodyColor1": lookup_code("VehBodyColor1", vehicle.get("color") or ""),
            "VehBankCode": lookup_code("VehBankCode", vehicle.get("bank_name") or ""),
            "VehWeightEmpty": str(vehicle.get("weight_empty") or ""),
            "VehWeightFull": str(vehicle.get("weight_full") or ""),
            "VehRemarks": str(payload.get("remarks") or ""),
            "QuotNo": quotation_no,
        }

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
        mock_payload = self.get_extra_config().get("mock_quote_response")
        if isinstance(mock_payload, dict):
            return self.build_quote_from_mapping(
                mock_payload,
                response_time_ms=int((time.perf_counter() - started) * 1000),
            )

        created = self.create_quote(payload)
        quotation_no = str(created.get("QuotationNo") or "")
        selected_covers = self._build_selected_covers(created)
        if not quotation_no or not selected_covers:
            raise ProviderRequestError("NIA create quote did not return a quotation with covers.")

        product = created.get("Data") or {}
        self.save_quote_with_plan(
            {
                "ReferenceNo": str(payload.get("reference_no") or ""),
                "SchemeCode": str(product.get("ProdCode") or ""),
                "ProductCode": str(product.get("ProdCode") or ""),
                "SelectedCovers": selected_covers,
            }
        )
        additional_info_payload = self._build_additional_info_request(payload, quotation_no)
        self.save_additional_info(additional_info_payload)
        documents_payload = self._build_documents_payload(payload, quotation_no)
        if documents_payload["docUpload"]:
            self.save_documents(documents_payload)

        total_premium = sum(Decimal(str(item.get("Premium") or 0)) for item in (created.get("Covers") or []))
        vat = Decimal("0")
        return self.build_quote_from_mapping(
            {
                "premium": total_premium,
                "vat": vat,
                "total": total_premium + vat,
                "currency": "AED",
                "plan_name": product.get("ProdName") or "NIA Plan",
                "quotation_no": quotation_no,
                "create_quote": created,
            },
            response_time_ms=int((time.perf_counter() - started) * 1000),
        )

    def issue_policy(self, payload: dict[str, Any]) -> dict[str, Any]:
        quot_no = str(payload.get("quotation_no") or payload.get("quot_no") or "")
        return self.approve_policy({"PolRefNo": quot_no, "PayType": payload.get("pay_type") or "OA"})

    def renew_policy(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.create_quote(payload)

    def fetch_policy(self, payload: dict[str, Any]) -> dict[str, Any]:
        quotation_no = str(payload.get("quotation_no") or payload.get("quot_no") or payload.get("policy_no") or "")
        return self.proposal_summary({"PolRefNo": quotation_no})

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

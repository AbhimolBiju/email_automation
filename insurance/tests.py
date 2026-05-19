import json
from pathlib import Path

from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from deals.models import Deal
from insurance.models import InsuranceProvider, QuoteBatch, QuoteRequestLog, QuoteResult
from insurance.providers.dic_masterdata import list_masterdata, lookup_code
from insurance.providers.dic_provider import DICProvider
from insurance.providers.nia_masterdata import load_sheet_records as load_nia_sheet_records
from insurance.providers.nia_masterdata import lookup_code as nia_lookup_code
from insurance.providers.nia_provider import NIAProvider
from insurance.providers.qic_masterdata import lookup_make_model_codes
from insurance.providers.qic_masterdata import lookup_nationality_code
from insurance.providers.qic_provider import QICProvider
from insurance.providers.factory import build_provider, resolve_provider_class
from insurance.services.quote_service import get_best_quotes, refresh_quote_batch
from leads.models import Lead


class InsuranceQuoteIntegrationTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="agent1",
            email="agent1@example.com",
            password="secret123",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.lead = Lead.objects.create(
            name="John Doe",
            email="john.doe@example.com",
            product_type="motor",
            mobile_number="+971500000001",
            responsible=self.user,
        )
        self.deal = Deal.objects.create(
            lead=self.lead,
            insurance_type="car_insurance_new",
            sub_type="comprehensive_agency",
            nationality="Indian",
            emirates_id="784-1987-1234567-1",
            stage_id=Deal.STAGE_AWAITING_ADDITIONAL_DOCUMENTS,
            reg_number="AUH-12345",
            chassis_number="VIN123456789",
            model_year=2025,
        )

    def _create_provider(self, *, name, code, priority, is_active=True, quote_total=1000):
        return InsuranceProvider.objects.create(
            name=name,
            code=code,
            priority=priority,
            is_active=is_active,
            provider_class=f"{code.lower()}_provider.{code.upper()}Provider",
            extra_config={
                "mock_quote_response": {
                    "premium": quote_total - 50,
                    "vat": 50,
                    "total": quote_total,
                    "currency": "AED",
                    "plan_name": f"{name} Comprehensive",
                },
                "mock_health_check": {"status": "ok"},
            },
        )

    def test_provider_factory_resolves_whitelisted_class(self):
        provider = self._create_provider(name="NIA", code="NIA", priority=1)
        provider_cls = resolve_provider_class(provider.provider_class)
        instance = build_provider(provider)

        self.assertEqual(provider_cls.__name__, "NIAProvider")
        self.assertEqual(instance.provider_code, "NIA")

    def test_get_best_quotes_uses_only_active_providers_and_sorts_by_total(self):
        self._create_provider(name="QIC", code="QIC", priority=3, quote_total=1325)
        self._create_provider(name="NIA", code="NIA", priority=1, quote_total=1450)
        self._create_provider(name="DIC", code="DIC", priority=2, quote_total=1180)
        InsuranceProvider.objects.create(
            name="Disabled",
            code="ZZZ",
            priority=99,
            is_active=False,
            provider_class="nia_provider.NIAProvider",
            extra_config={"mock_quote_response": {"premium": 850, "vat": 50, "total": 900}},
        )

        result = get_best_quotes(self.deal.id)

        self.assertEqual(result["requested_provider_count"], 3)
        self.assertEqual(result["successful_provider_count"], 3)
        self.assertEqual(result["batch"]["best_provider"], "DIC")
        self.assertEqual([quote["provider"] for quote in result["results"]], ["DIC", "QIC", "NIA"])
        self.assertEqual(QuoteBatch.objects.count(), 1)
        self.assertEqual(QuoteRequestLog.objects.count(), 3)
        self.assertEqual(QuoteResult.objects.count(), 3)

    def test_refresh_quote_batch_reuses_existing_batch(self):
        self._create_provider(name="NIA", code="NIA", priority=1, quote_total=1450)
        self._create_provider(name="DIC", code="DIC", priority=2, quote_total=1180)

        initial = get_best_quotes(self.deal.id)
        batch_id = initial["batch"]["id"]

        refresh_quote_batch(batch_id)

        self.assertEqual(QuoteBatch.objects.count(), 1)
        self.assertEqual(QuoteBatch.objects.first().id, batch_id)

    def test_get_best_quotes_allows_partial_success(self):
        self._create_provider(name="NIA", code="NIA", priority=1, quote_total=1450)
        InsuranceProvider.objects.create(
            name="Broken QIC",
            code="QIC",
            priority=2,
            is_active=True,
            provider_class="qic_provider.QICProvider",
            extra_config={"health_endpoint": "/missing"},
        )

        result = get_best_quotes(self.deal.id)

        self.assertEqual(result["requested_provider_count"], 2)
        self.assertEqual(result["successful_provider_count"], 1)
        self.assertEqual(len(result["failures"]), 1)
        self.assertEqual(result["results"][0]["provider"], "NIA")
        self.assertEqual(
            QuoteRequestLog.objects.filter(status=QuoteRequestLog.STATUS_FAILED).count(),
            1,
        )
        self.assertEqual(QuoteBatch.objects.first().status, QuoteBatch.STATUS_PARTIAL_SUCCESS)

    def test_quote_endpoint_returns_normalized_output(self):
        self._create_provider(name="NIA", code="NIA", priority=1, quote_total=1450)
        self._create_provider(name="DIC", code="DIC", priority=2, quote_total=1180)

        response = self.client.post(f"/insurance/deals/{self.deal.id}/quotes/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["data"]["successful_provider_count"], 2)
        self.assertEqual(
            sorted(payload["data"]["results"][0].keys()),
            sorted(
                [
                    "provider",
                    "provider_name",
                    "logo",
                    "premium",
                    "vat",
                    "total",
                    "currency",
                    "plan_name",
                    "response_time_ms",
                    "ranking",
                    "coverage_score",
                    "status",
                    "error_message",
                    "normalized_response",
                    "raw_response",
                    "recommended",
                    "is_cheapest",
                    "is_best_value",
                    "created_at",
                    "id",
                ]
            ),
        )

    def test_provider_list_masks_secrets(self):
        InsuranceProvider.objects.create(
            name="NIA",
            code="NIA",
            priority=1,
            is_active=True,
            provider_class="nia_provider.NIAProvider",
            api_key="supersecretkey",
            password="verysecretpassword",
        )

        response = self.client.get("/insurance/providers/")

        self.assertEqual(response.status_code, 200)
        provider = response.json()["data"][0]
        self.assertNotIn("api_key", provider)
        self.assertNotIn("password", provider)
        self.assertNotIn("extra_config", provider)
        self.assertTrue(provider["masked_api_key"].startswith("su"))
        self.assertGreater(len(provider["masked_password"]), 0)


class DICProviderTests(TestCase):
    def setUp(self):
        self.provider_config = InsuranceProvider.objects.create(
            name="DIC",
            code="DIC",
            priority=1,
            is_active=True,
            provider_class="dic_provider.DICProvider",
            base_url="https://uatbrokerportal.dubins.ae",
            username="MOTOR_USER_001",
            password="secret",
            extra_config={
                "mock_token": "mock-dic-token",
                "mock_generate_quote_response": [
                    {
                        "prodCode": "1001",
                        "prodName": {"en": "1001 - Comprehensive Gold", "ar": "1001 - Comprehensive Gold"},
                        "covers": {
                            "mandatory": [
                                {"coverCode": "10001", "premium": 4409.6},
                                {"coverCode": "10006", "premium": 35},
                            ],
                            "optional": [],
                        },
                    },
                    {
                        "prodCode": "1521",
                        "prodName": {"en": "1521 - Motor Third Party Liability", "ar": "1521 - Motor Third Party Liability"},
                        "covers": {
                            "mandatory": [
                                {"coverCode": "15001", "premium": 1100},
                                {"coverCode": "15002", "premium": 0},
                            ],
                            "optional": [],
                        },
                    },
                ],
            },
        )
        self.provider = DICProvider(self.provider_config)

    def _sample_quote_payload(self):
        return {
            "customer": {
                "name": "Shreyaa",
                "nationality": "Indian",
                "emirates_id": "35363735322",
                "emirates_id_expiry_date": "21/10/2038",
                "date_of_birth": "14/10/1997",
                "gender": "Female",
                "emirate": "RAS AL-KHAIMAH",
                "email": "shreyash@gmail.com",
                "mobile_number": "97135687632",
            },
            "vehicle": {
                "license_number": "35372179989",
                "license_from_date": "21/05/2017",
                "license_to_date": "28/11/2038",
                "chassis_number": "JTJHY00W0J4282051",
                "registration_number": "6562",
                "registration_date": "17/07/2020",
                "plate_code": "E",
                "plate_source": "DUBAI",
                "tcf_number": "343",
                "ncd_years": "2 Years",
                "traffic_transaction_type": "New Vehicle Registration",
                "is_vehicle_brand_new": False,
                "agency_repair": False,
            },
            "document_lists": [
                {
                    "code": "107",
                    "name": "BankLpo",
                    "base64": "ZmFrZS1pbWFnZQ==",
                    "type": "png",
                }
            ],
        }

    def test_dic_masterdata_lookup_works_with_description_and_code(self):
        self.assertEqual(lookup_code("nationality", "Indian"), "101")
        self.assertEqual(lookup_code("emirate", "04"), "04")
        self.assertGreater(len(list_masterdata("bank_name")), 100)

    def test_dic_generate_quote_request_maps_masterdata(self):
        request_payload = self.provider._build_generate_quote_request(self._sample_quote_payload())

        self.assertEqual(request_payload["nationality"], "101")
        self.assertEqual(request_payload["gender"], "F")
        self.assertEqual(request_payload["emirate"], "03")
        self.assertEqual(request_payload["PlateSource"], "0001")
        self.assertEqual(request_payload["plateSource"], "0001")
        self.assertEqual(request_payload["ncdYears"], "2")
        self.assertEqual(request_payload["trafficTranType"], "101")
        self.assertEqual(request_payload["dateOfBirth"], "14/10/1997")
        self.assertEqual(request_payload["licenseFmDt"], "21/05/2017")
        self.assertEqual(len(request_payload["documentLists"]), 1)

    def test_dic_get_quote_selects_cheapest_scheme(self):
        chosen_scheme_calls = []

        def fake_choose_scheme(payload, *, request_id):
            chosen_scheme_calls.append((payload, request_id))
            if payload["prodCode"] == "1001":
                return {
                    "quotationNo": "PQ-GOLD",
                    "grossPremium": 4444.6,
                    "netPremium": 4444.6,
                    "vat": 222.23,
                    "netToCustomer": 4666.83,
                    "scheme": "1001 - Comprehensive Gold",
                }
            return {
                "quotationNo": "PQ-TP",
                "grossPremium": 1100,
                "netPremium": 1100,
                "vat": 55,
                "netToCustomer": 1155,
                "scheme": "1521 - Motor Third Party Liability",
            }

        self.provider.choose_scheme = fake_choose_scheme

        quote = self.provider.get_quote(self._sample_quote_payload())
        data = quote.as_dict(include_raw_response=True)

        self.assertEqual(data["provider"], "DIC")
        self.assertEqual(data["total"], 1155.0)
        self.assertEqual(data["plan_name"], "1521 - Motor Third Party Liability")
        self.assertEqual(len(chosen_scheme_calls), 2)
        self.assertTrue(data["raw_response"]["request_id"])

    def test_dic_payment_info_can_be_used_as_policy_fetch(self):
        self.provider.get_payment_info = lambda **kwargs: {
            "polNo": "P/13/1001/25/020/00001",
            "documents": "UERG",
        }

        result = self.provider.download_policy_documents({"policy_no": "P/13/1001/25/020/00001"})

        self.assertEqual(result["policy_no"], "P/13/1001/25/020/00001")
        self.assertEqual(result["documents_base64"], "UERG")


class QICProviderTests(TestCase):
    def setUp(self):
        self.provider_config = InsuranceProvider.objects.create(
            name="QIC",
            code="QIC",
            priority=1,
            is_active=True,
            provider_class="qic_provider.QICProvider",
            base_url="https://www.devapi.anoudapps.com",
            username="qic-user",
            password="qic-pass",
            extra_config={"company_code": "002"},
        )
        self.provider = QICProvider(self.provider_config)

    def test_qic_basic_authenticate_returns_basic_token(self):
        token = self.provider.authenticate()
        self.assertTrue(token)
        self.assertIn("Authorization", self.provider.get_auth_headers())

    def test_qic_get_quote_selects_lowest_net_premium(self):
        self.provider.get_tariff = lambda payload: {
            "quoteNo": "26200013010",
            "products": [
                {"productCode": "0110", "schemes": [{"schemeCode": "0297", "schemeDescription": "Comprehensive"}]},
                {"productCode": "0150", "schemes": [{"schemeCode": "0401", "schemeDescription": "Third Party"}]},
            ],
        }
        premiums = {
            ("0110", "0297"): {"netPremium": 1386.53, "taxAmount": 66.03},
            ("0150", "0401"): {"netPremium": 1155, "taxAmount": 55},
        }
        self.provider.get_net_premium = lambda payload: premiums[
            (
                payload["schemes"][0]["productCode"],
                payload["schemes"][0]["schemeCode"],
            )
        ]

        quote = self.provider.get_quote(
            {
                "customer": {"name": "John", "nationality": "Indian", "date_of_birth": "01/01/1990"},
                "vehicle": {"make_id": "Acura", "model_id": "MDX", "body_type_id": "4 X 4", "engine_capacity_id": "4", "model_year": "2022", "chassis_number": "VIN123"},
            }
        )
        data = quote.as_dict(include_raw_response=True)

        self.assertEqual(data["provider"], "QIC")
        self.assertEqual(data["total"], 1155.0)
        self.assertEqual(data["plan_name"], "Third Party")


class NIAProviderTests(TestCase):
    def setUp(self):
        self.provider_config = InsuranceProvider.objects.create(
            name="NIA",
            code="NIA",
            priority=1,
            is_active=True,
            provider_class="nia_provider.NIAProvider",
            base_url="https://portal.nia.example",
            username="nia@example.com",
            password="nia-pass",
            extra_config={"mock_token": "nia-token"},
        )
        self.provider = NIAProvider(self.provider_config)

    def test_nia_authenticate_uses_mock_token(self):
        self.assertEqual(self.provider.authenticate(), "nia-token")

    def test_nia_get_quote_computes_total_from_selected_covers(self):
        self.provider.create_quote = lambda payload: {
            "QuotationNo": "Q/MOT/162428",
            "Data": {"ProdCode": "1002", "ProdName": "Motor Comprehensive –Non Agency"},
            "Covers": [
                {"Code": "1001", "Premium": "1470", "Selected": "Y"},
                {"Code": "1002", "Premium": "750", "Selected": "Y"},
                {"Code": "1007", "Premium": "0", "Selected": "N"},
            ],
        }
        self.provider.save_quote_with_plan = lambda payload: {"Status": 1}
        self.provider.save_additional_info = lambda payload: {"Status": 1}
        self.provider.save_documents = lambda payload: {"Status": 1}

        quote = self.provider.get_quote(
            {
                "customer": {
                    "name": "John",
                    "nationality": "INDIAN",
                    "date_of_birth": "01/01/1990",
                    "email": "john@example.com",
                    "mobile_number": "97150000000",
                    "emirates_id": "784-1990-0000000-1",
                    "occupation": "ACCOUNTANT",
                    "emirate": "DUBAI",
                    "gender": "Male",
                },
                "vehicle": {
                    "chassis_number": "VIN123",
                    "make_id": "AUDI",
                    "model_id": "A3 BASE",
                    "body_type_id": "SALOON",
                    "engine_capacity_id": "4 CYLINDERS",
                    "registration_date": "01/01/2022",
                    "model_year": "2022",
                    "is_gcc_spec": True,
                    "agency_repair": False,
                    "is_vehicle_brand_new": False,
                    "traffic_transaction_type": "Vehicle Renewal",
                },
                "documents": [],
            }
        )
        data = quote.as_dict(include_raw_response=True)

        self.assertEqual(data["provider"], "NIA")
        self.assertEqual(data["premium"], 2220.0)
        self.assertEqual(data["total"], 2220.0)
        self.assertEqual(data["plan_name"], "Motor Comprehensive –Non Agency")
from pathlib import Path
from django.conf import settings
class ProviderMasterdataBuildTests(TestCase):
    
    

    def test_build_provider_masterdata_command_writes_dic_json(self):
        call_command("build_provider_masterdata", "--provider", "dic", "--force")

        json_path = Path(settings.BASE_DIR) / "data/providers/DIC/json/nationality.json"
        self.assertTrue(json_path.exists())

        payload = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["metadata"]["source_file"], "Nationality.xlsx")
        self.assertGreater(len(payload["records"]), 100)
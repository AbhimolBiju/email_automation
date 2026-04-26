from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from deals.models import Deal
from insurance.models import InsuranceProvider, QuoteRequestLog, QuoteResult
from insurance.providers.dic_masterdata import list_masterdata, lookup_code
from insurance.providers.dic_provider import DICProvider
from insurance.providers.factory import build_provider, resolve_provider_class
from insurance.services.quote_service import get_best_quotes
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
        self.assertEqual([quote["provider"] for quote in result["quotes"]], ["DIC", "QIC", "NIA"])
        self.assertEqual(QuoteRequestLog.objects.count(), 3)
        self.assertEqual(QuoteResult.objects.count(), 3)

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
        self.assertEqual(result["quotes"][0]["provider"], "NIA")
        self.assertEqual(
            QuoteRequestLog.objects.filter(status=QuoteRequestLog.STATUS_FAILED).count(),
            1,
        )

    def test_quote_endpoint_returns_normalized_output(self):
        self._create_provider(name="NIA", code="NIA", priority=1, quote_total=1450)
        self._create_provider(name="DIC", code="DIC", priority=2, quote_total=1180)

        response = self.client.post(f"/insurance/deals/{self.deal.id}/quotes/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["data"]["successful_provider_count"], 2)
        self.assertEqual(
            sorted(payload["data"]["quotes"][0].keys()),
            sorted(
                [
                    "provider",
                    "premium",
                    "vat",
                    "total",
                    "currency",
                    "plan_name",
                    "response_time_ms",
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
        self.assertEqual(request_payload["plateSource"], "0001")
        self.assertEqual(request_payload["ncdYears"], "2")
        self.assertEqual(request_payload["trafficTranType"], "101")
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

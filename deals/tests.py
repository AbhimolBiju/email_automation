from django.test import TestCase
from rest_framework.test import APIRequestFactory

from deals.models import Deal
from deals.views import deals_board
from leads.models import GeneralDetails, Lead, MedicalDetails


class DealsBoardTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def get_board(self, query_string=""):
        request = self.factory.get(f"/deals/board/{query_string}")
        response = deals_board(request)
        self.assertEqual(response.status_code, 200)
        return response.data

    def test_board_exposes_motor_deal_as_generic_product_item(self):
        lead = Lead.objects.create(
            name="Motor Customer",
            email="motor@example.com",
            stage="sales_qualified_lead",
            status="QUALIFIED",
            product_type="motor",
        )
        deal = Deal.objects.create(
            lead=lead,
            stage_id=3,
            insurance_type="car_insurance_new",
            sub_type="third_party",
        )
        lead.motor_product = deal
        lead.save(update_fields=["motor_product"])

        board = self.get_board("?stages=3")

        stage = board[0]
        self.assertEqual(stage["stage_id"], 3)
        self.assertEqual(stage["total_count"], 1)
        self.assertEqual(stage["deal_count"], 1)
        self.assertNotIn("items", stage)

        item = stage["deals"][0]
        self.assertEqual(item["item_id"], f"motor:{deal.id}")
        self.assertEqual(item["record_kind"], "product")
        self.assertEqual(item["product_type"], "motor")
        self.assertEqual(item["product_table"], "motor_details")
        self.assertEqual(item["product_id"], deal.id)
        self.assertFalse(item["is_synthetic"])
        self.assertEqual(item["product"]["insurance_type"], "car_insurance_new")

        product_tables = {
            product["table"] for product in item["lead_details"]["products"]
        }
        self.assertIn("motor_details", product_tables)

    def test_board_exposes_lead_product_pointers_for_non_motor_tables(self):
        general = GeneralDetails.objects.create()
        medical = MedicalDetails.objects.create()
        lead = Lead.objects.create(
            name="Multi Product Customer",
            email="multi@example.com",
            stage="sales_qualified_lead",
            status="QUALIFIED",
            product_type="general",
            general_product=general,
            medical_product=medical,
        )

        board = self.get_board("?stages=1")

        self.assertNotIn("items", board[0])
        item = board[0]["deals"][0]
        self.assertEqual(item["item_id"], f"lead:{lead.id}")
        self.assertEqual(item["record_kind"], "lead")
        self.assertTrue(item["is_synthetic"])
        self.assertIsNone(item["product_table"])
        self.assertIsNone(item["product_id"])

        products = item["lead_details"]["products"]
        self.assertEqual(
            {(product["type"], product["table"], product["id"]) for product in products},
            {
                ("general", "general_details", general.id),
                ("medical", "medical_details", medical.id),
            },
        )

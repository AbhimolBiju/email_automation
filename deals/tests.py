from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from pathlib import Path
from rest_framework.test import APIRequestFactory

from deals.models import Deal
from deals.views import deal_detail, deals_board, upload_deal_document
from documents.models import Document
from leads.models import GeneralDetails, Lead, MedicalDetails
from deals.serializers import DealCreateSerializer


@override_settings(MEDIA_ROOT=Path("/tmp/promise_backend_test_media"))
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


@override_settings(MEDIA_ROOT=Path("/tmp/promise_backend_test_media"))
class DealCreateSerializerTests(TestCase):
    def test_create_sets_stage_to_awaiting_additional_documents(self):
        lead = Lead.objects.create(
            name="Create Flow Customer",
            email="create-flow@example.com",
            status="QUALIFIED",
            stage="sales_qualified_lead",
            product_type="motor",
        )
        serializer = DealCreateSerializer(
            data={
                "lead": lead.id,
                "stage_id": Deal.STAGE_POTENTIAL_CUSTOMER,
                "insurance_type": "car_insurance_new",
                "sub_type": "third_party",
                "driving_license_front": SimpleUploadedFile(
                    "license-front.txt", b"front", content_type="text/plain"
                ),
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        deal = serializer.save()

        self.assertEqual(
            deal.stage_id,
            Deal.STAGE_AWAITING_ADDITIONAL_DOCUMENTS,
        )
        document = Document.objects.get(motor_deal=deal)
        self.assertEqual(document.document_type, "driving_license_front")
        self.assertEqual(document.source, "deal_form")

    def test_create_attaches_pre_uploaded_document_ids(self):
        lead = Lead.objects.create(
            name="Uploaded Doc Customer",
            email="uploaded-doc@example.com",
            status="QUALIFIED",
            stage="sales_qualified_lead",
            product_type="motor",
        )
        document = Document.objects.create(
            document_type="emirates_id_front",
            file=SimpleUploadedFile(
                "eid-front.txt", b"eid", content_type="text/plain"
            ),
            source="deal_form_upload",
        )

        serializer = DealCreateSerializer(
            data={
                "lead": lead.id,
                "insurance_type": "car_insurance_new",
                "sub_type": "third_party",
                "document_ids": [document.id],
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        deal = serializer.save()

        document.refresh_from_db()
        self.assertEqual(document.motor_deal, deal)
        self.assertEqual(document.source, "deal_form")


@override_settings(MEDIA_ROOT=Path("/tmp/promise_backend_test_media"))
class DealDocumentUploadTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_upload_deal_document_returns_document_id(self):
        request = self.factory.post(
            "/deals/documents/upload/",
            {
                "document_type": "driving_license_front",
                "file": SimpleUploadedFile(
                    "license-front.txt", b"front", content_type="text/plain"
                ),
            },
            format="multipart",
        )

        response = upload_deal_document(request)

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["success"])
        self.assertIsNotNone(response.data["data"]["id"])
        document = Document.objects.get(id=response.data["data"]["id"])
        self.assertIsNone(document.motor_deal)
        self.assertEqual(document.source, "deal_form_upload")


@override_settings(MEDIA_ROOT=Path("/tmp/promise_backend_test_media"))
class DealDetailEditTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_deal_detail_returns_lead_and_documents_for_editing(self):
        lead = Lead.objects.create(
            name="Edit Customer",
            email="edit@example.com",
            mobile_number="+971501234567",
            phone_number="+971501234567",
            status="QUALIFIED",
            stage="sales_qualified_lead",
            product_type="motor",
        )
        deal = Deal.objects.create(
            lead=lead,
            nationality="UAE",
            emirates_id="784-1990-1234567-1",
            stage_id=Deal.STAGE_QUOTATION,
        )
        document = Document.objects.create(
            motor_deal=deal,
            document_type="driving_license_front",
            file=SimpleUploadedFile(
                "license-front.txt", b"front", content_type="text/plain"
            ),
            source="deal_form",
            status=Document.STATUS_VERIFIED,
        )
        Document.objects.create(
            motor_deal=deal,
            document_type="emirates_id_front",
            file=SimpleUploadedFile(
                "eid-front.txt", b"front", content_type="text/plain"
            ),
            source="deal_form",
            status=Document.STATUS_REJECTED,
        )

        request = self.factory.get(f"/deals/{deal.id}/")
        response = deal_detail(request, deal.id)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        payload = response.data["data"]
        self.assertEqual(payload["id"], deal.id)
        self.assertEqual(payload["lead"]["id"], lead.id)
        self.assertEqual(payload["lead"]["name"], "Edit Customer")
        self.assertEqual(len(payload["documents"]), 1)
        self.assertEqual(payload["documents"][0]["id"], document.id)
        self.assertEqual(payload["documents"][0]["document_type"], "driving_license_front")
        self.assertEqual(payload["stage_label"], "Quotation")

    def test_deal_patch_updates_deal_lead_and_attaches_documents(self):
        lead = Lead.objects.create(
            name="Old Customer",
            email="old@example.com",
            mobile_number="+971500000000",
            phone_number="+971500000000",
            status="QUALIFIED",
            stage="sales_qualified_lead",
            product_type="motor",
        )
        deal = Deal.objects.create(
            lead=lead,
            nationality="UAE",
            emirates_id="OLD-ID",
            stage_id=Deal.STAGE_POTENTIAL_CUSTOMER,
        )
        document = Document.objects.create(
            document_type="emirates_id_front",
            file=SimpleUploadedFile("eid-front.txt", b"eid", content_type="text/plain"),
            source="deal_form_upload",
        )

        request = self.factory.patch(
            f"/deals/{deal.id}/",
            {
                "name": "New Customer",
                "email": "new@example.com",
                "mobile_number": "+971511111111",
                "nationality": "India",
                "emirates_id": "NEW-ID",
                "document_ids": [document.id],
            },
            format="json",
        )
        response = deal_detail(request, deal.id)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])

        deal.refresh_from_db()
        lead.refresh_from_db()
        document.refresh_from_db()
        self.assertEqual(deal.nationality, "India")
        self.assertEqual(deal.emirates_id, "NEW-ID")
        self.assertEqual(deal.stage_id, Deal.STAGE_AWAITING_ADDITIONAL_DOCUMENTS)
        self.assertEqual(lead.name, "New Customer")
        self.assertEqual(lead.email, "new@example.com")
        self.assertEqual(lead.mobile_number, "+971511111111")
        self.assertEqual(document.motor_deal, deal)
        self.assertEqual(document.source, "deal_form")

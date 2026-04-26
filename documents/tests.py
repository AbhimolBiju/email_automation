from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from pathlib import Path
from unittest.mock import patch
from rest_framework.test import APIRequestFactory

from deals.models import Deal
from documents.management.commands.backfill_ocr_data import normalized_from_existing_response
from documents.models import Document, unique_document_upload_path
from documents.ocr_parser import extract_structured_fields
from documents.ocr_service import OCRResult, process_document_ocr
from documents.views import document_list, fetch_document_ocr, ocr_stats, reupload_document_file
from leads.models import Lead


@override_settings(
    DOCUMENT_OCR_AUTO_PROCESS=False,
    MEDIA_ROOT=Path("/tmp/promise_backend_test_media"),
)
class DocumentViewsTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_document_list_reads_shared_document_table(self):
        lead = Lead.objects.create(
            name="Doc Review Customer",
            email="doc-review@example.com",
            stage="sales_qualified_lead",
            status="QUALIFIED",
            product_type="motor",
        )
        deal = Deal.objects.create(lead=lead, stage_id=2)
        document = Document.objects.create(
            motor_deal=deal,
            name="emirates-id-front.png",
            document_type="emirates_id_front",
            status=Document.STATUS_LOW_CONFIDENCE,
            score=72,
        )

        response = document_list(self.factory.get("/documents/documents/"))

        self.assertEqual(response.status_code, 200)
        row = response.data["data"][0]
        self.assertEqual(row["document_id"], f"DOC-{document.id:04d}")
        self.assertEqual(row["lead_id"], f"LD-{lead.id:04d}")
        self.assertEqual(row["first_name"], lead.name)
        self.assertEqual(row["product"], "Motor")
        self.assertEqual(row["confidence_score"], 72)
        self.assertEqual(row["status"], "Low-confidence")

    def test_ocr_stats_uses_shared_document_statuses(self):
        Document.objects.create(name="verified.pdf", status=Document.STATUS_VERIFIED)
        Document.objects.create(name="pending.pdf", status=Document.STATUS_PENDING)
        Document.objects.create(
            name="low-confidence.pdf",
            status=Document.STATUS_LOW_CONFIDENCE,
        )

        response = ocr_stats(self.factory.get("/documents/status/"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["total_documents"], 3)
        self.assertEqual(response.data["data"]["verified_count"], 1)
        self.assertEqual(response.data["data"]["pending_review"], 1)
        self.assertEqual(response.data["data"]["low_confidence_count"], 1)

    def test_document_upload_path_uses_unique_name(self):
        first = unique_document_upload_path(None, "license front.JPG")
        second = unique_document_upload_path(None, "license front.JPG")

        self.assertTrue(first.startswith("documents/"))
        self.assertTrue(first.endswith(".jpg"))
        self.assertNotEqual(first, second)

    def test_document_file_save_uses_unique_name(self):
        first = Document.objects.create(
            file=SimpleUploadedFile("same-name.txt", b"one", content_type="text/plain")
        )
        second = Document.objects.create(
            file=SimpleUploadedFile("same-name.txt", b"two", content_type="text/plain")
        )

        self.assertNotEqual(first.file.name, second.file.name)
        self.assertTrue(first.file.name.startswith("documents/"))

    @patch("documents.views.enqueue_document_ocr")
    def test_fetch_document_ocr_queues_for_existing_file(self, enqueue_document_ocr):
        document = Document.objects.create(
            file=SimpleUploadedFile("license.txt", b"ocr", content_type="text/plain"),
            ocr_status=Document.OCR_FAILED,
        )

        response = fetch_document_ocr(
            self.factory.post(f"/documents/{document.id}/fetch-ocr/"),
            document.id,
        )

        self.assertEqual(response.status_code, 202)
        document.refresh_from_db()
        self.assertEqual(document.ocr_status, Document.OCR_PENDING)
        enqueue_document_ocr.assert_called_once_with(document.id, force=True)

    @patch("documents.ocr_service.run_azure_read_model")
    def test_ocr_keeps_uploaded_document_type(self, run_azure_read_model):
        run_azure_read_model.return_value = OCRResult(
            provider_response={"engine": "test", "raw_text": "Identity Card"},
            ocr_data={"document_type": "emirates_id", "full_name": "Test User"},
            confidence=0.95,
            document_type="emirates_id",
        )
        document = Document.objects.create(
            document_type="emirates_id_front",
            file=SimpleUploadedFile("eid-front.txt", b"ocr", content_type="text/plain"),
        )

        process_document_ocr(document.id, force=True)

        document.refresh_from_db()
        self.assertEqual(document.document_type, "emirates_id_front")
        self.assertEqual(document.ocr_data["document_type"], "emirates_id")

    def test_reupload_creates_new_document_and_preserves_original(self):
        lead = Lead.objects.create(
            name="Reupload Customer",
            email="reupload@example.com",
            stage="sales_qualified_lead",
            status="QUALIFIED",
            product_type="motor",
        )
        deal = Deal.objects.create(lead=lead, stage_id=2)
        original = Document.objects.create(
            motor_deal=deal,
            document_type="emirates_id_front",
            file=SimpleUploadedFile(
                "old.png",
                b"old",
                content_type="image/png",
            ),
            ocr_status=Document.OCR_SUCCESS,
            status=Document.STATUS_REJECTED,
        )

        request = self.factory.post(
            f"/documents/{original.id}/reupload/",
            {
                "file": SimpleUploadedFile(
                    "new.png",
                    b"new",
                    content_type="image/png",
                )
            },
            format="multipart",
        )

        response = reupload_document_file(request, original.id)

        self.assertEqual(response.status_code, 201)
        original.refresh_from_db()
        new_document = Document.objects.get(id=response.data["data"]["id"])
        self.assertEqual(original.status, Document.STATUS_REJECTED)
        self.assertEqual(new_document.reuploaded_from_id, original.id)
        self.assertEqual(new_document.document_type, original.document_type)
        self.assertEqual(new_document.motor_deal_id, deal.id)
        self.assertEqual(new_document.status, Document.STATUS_PENDING)
        self.assertEqual(new_document.ocr_status, Document.OCR_PENDING)
        self.assertNotEqual(new_document.file.name, original.file.name)


class OCRParserTests(TestCase):
    def test_extracts_emirates_id_fields_from_read_text(self):
        payload = extract_structured_fields(
            """
            United Arab Emirates Identity Card
            Name: John Mathew
            Nationality: Indian
            ID Number: 784-1987-1234567-1
            Date of Birth: 15/01/1987
            Expiry Date: 10/04/2028
            """,
            confidence=0.94,
        )

        self.assertEqual(payload["document_type"], "emirates_id")
        self.assertEqual(payload["full_name"], "John Mathew")
        self.assertEqual(payload["nationality"], "Indian")
        self.assertEqual(payload["emirates_id"], "784-1987-1234567-1")
        self.assertEqual(payload["dob"], "1987-01-15")
        self.assertEqual(payload["expiry_date"], "2028-04-10")
        self.assertNotIn("raw_text", payload)
        self.assertNotIn("confidence", payload)

    def test_extracts_vehicle_and_policy_fields_from_read_text(self):
        payload = extract_structured_fields(
            """
            Certificate of Insurance
            Policy No: POL-2026-4455
            Chassis No: JE4M4Y185SZ705308
            Plate No: DXB 12345
            Issue Date: 25 Apr 2026
            """,
            confidence=0.88,
        )

        self.assertEqual(payload["document_type"], "insurance_policy")
        self.assertEqual(payload["policy_no"], "POL-2026-4455")
        self.assertEqual(payload["chassis_no"], "JE4M4Y185SZ705308")
        self.assertEqual(payload["plate_no"], "DXB 12345")
        self.assertEqual(payload["issue_date"], "2026-04-25")

    def test_extracts_vehicle_registration_from_bilingual_ocr_order(self):
        payload = extract_structured_fields(
            """
            بيانات المركبة
            Vehicle Information
            عدد الركاب
            7
            .Num. of Pass | سنة الصنع
            2025
            Model
            اليابان
            صنف المركبة
            استيشن.
            MITSUBISHI OUTLANDER
            Veh. Type
            1715
            Empty Weight|الوزن الاجمالي
            2
            G. V. W.
            رقم المحرك
            PR25033 525045F
            Eng. No.
            رقم القاعدة
            JE4M4Y185SZ705308
            Chassis No.
            UAE
            سلطة الترخيص RTA Licensing Authority
            Japan
            Origin
            بلد الصنع لون المركبة نوع المركبة الوزن فارغة
            ابيض
            MITSUBISHI OUTLANDER
            """,
            confidence=0.95,
        )

        self.assertEqual(payload["document_type"], "vehicle_registration")
        self.assertEqual(payload["manufacturer"], "MITSUBISHI")
        self.assertEqual(payload["model"], "OUTLANDER")
        self.assertEqual(payload["vehicle_name"], "MITSUBISHI OUTLANDER")
        self.assertEqual(payload["year"], "2025")
        self.assertEqual(payload["origin"], "Japan")
        self.assertEqual(payload["chassis_no"], "JE4M4Y185SZ705308")
        self.assertEqual(payload["engine_no"], "PR25033525045F")
        self.assertEqual(payload["color"], "White")
        self.assertEqual(payload["passenger_capacity"], "7")

    def test_backfill_normalizes_existing_mixed_ocr_response(self):
        document = Document.objects.create(
            document_type="other",
            ocr_response={
                "engine": "azure_document_intelligence",
                "model_id": "prebuilt-read",
                "confidence": 0.95,
                "raw_text": "Passport\nName: Jane Mathew\nPassport No: A12345678",
            },
        )

        payload = normalized_from_existing_response(document)

        self.assertEqual(payload["document_type"], "passport")
        self.assertEqual(payload["full_name"], "Jane Mathew")
        self.assertEqual(payload["passport_no"], "A12345678")

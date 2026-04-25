from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch
from rest_framework.test import APIRequestFactory

from deals.models import Deal
from documents.models import Document, unique_document_upload_path
from documents.ocr_parser import extract_structured_fields
from documents.views import document_list, fetch_document_ocr, ocr_stats
from leads.models import Lead


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
        self.assertEqual(payload["confidence"], 0.94)

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

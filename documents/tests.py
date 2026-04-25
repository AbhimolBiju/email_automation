from django.test import TestCase
from rest_framework.test import APIRequestFactory

from deals.models import Deal
from documents.models import Document
from documents.views import document_list, ocr_stats
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

from decimal import Decimal

from django.test import SimpleTestCase

from apps.invoice.services.calculation_builder import build_calculation_from_documents


class CalculationBuilderTests(SimpleTestCase):
    def test_debit_customer_and_credit_insurance_company(self):
        result = build_calculation_from_documents(
            {
                "net_premium": "12370.76",
                "vat_amount": "618.54",
                "total_amount": "12989.30",
            },
            {
                "commission_percentage": "15",
                "commission_amount": "1855.61",
                "vat_amount": "92.78",
            },
        )

        self.assertEqual(result["customer"]["net_premium"], "12370.76")
        self.assertEqual(result["customer"]["vat_amount"], "618.54")
        self.assertEqual(result["customer"]["total_premium"], "12989.30")
        self.assertEqual(result["customer"]["net_due"], "12989.30")

        self.assertEqual(result["insurance_company"]["net_premium"], "12370.76")
        self.assertEqual(result["insurance_company"]["commission_percent"], "15.00")
        self.assertEqual(result["insurance_company"]["commission_amount"], "1855.61")
        self.assertEqual(result["insurance_company"]["vat_amount"], "92.78")
        self.assertEqual(result["insurance_company"]["net_due"], "11040.91")

    def test_derives_total_when_missing(self):
        result = build_calculation_from_documents(
            {"net_premium": "100.00", "vat_amount": "5.00"},
            {"commission_amount": "10.00", "vat_amount": "1.00"},
        )

        self.assertEqual(result["customer"]["total_premium"], "105.00")
        self.assertEqual(result["insurance_company"]["net_due"], "94.00")

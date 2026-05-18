from django.test import SimpleTestCase

from apps.invoice.services.parser.commission_utils import resolve_commission_fields
from apps.invoice.services.parser.router import normalize_parser_output


class CommissionUtilsTests(SimpleTestCase):
    def test_resolve_from_commission_items(self) -> None:
        result = resolve_commission_fields(
            {
                "commission_items": [
                    {
                        "commission_percentage": "15",
                        "commission_amount": "1855.61",
                    },
                ],
            },
        )
        self.assertEqual(result["commission_percentage"], "15")
        self.assertEqual(result["commission_amount"], 1855.61)

    def test_resolve_sum_own_damage_and_third_party(self) -> None:
        result = resolve_commission_fields(
            {
                "own_damage_commission_percentage": "10",
                "own_damage_commission_amount": "500.00",
                "third_party_commission_percentage": "10",
                "third_party_commission_amount": "300.00",
            },
        )
        self.assertEqual(result["commission_amount"], 800.0)
        self.assertEqual(result["commission_percentage"], "10")

    def test_normalize_applies_commission_resolution(self) -> None:
        result = normalize_parser_output(
            {
                "commission_items": [
                    {
                        "commission_percentage": "12.5",
                        "commission_amount": "1000.00",
                    },
                ],
            },
        )
        self.assertEqual(result["commission_percentage"], "12.5")
        self.assertEqual(result["commission_amount"], 1000.0)

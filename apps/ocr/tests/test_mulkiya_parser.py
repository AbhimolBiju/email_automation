"""Tests for Mulkiya OCR text parsing."""

from __future__ import annotations

from django.test import SimpleTestCase

from apps.ocr.services.mulkiya_parser import (
    _registration_date_from_azure_layout,
    _traffic_plate_from_azure_layout,
    parse_mulkiya_back,
    parse_mulkiya_front,
)


class MulkiyaParserTests(SimpleTestCase):
    """Tests for UAE Mulkiya field extraction from OCR text."""

    def test_parse_mulkiya_front_registration_date(self) -> None:
        """Front side should extract registration date from label lines."""
        text = """
        Vehicle License
        Registration Date
        17/07/2020
        Traffic Plate No
        12345
        """
        data = parse_mulkiya_front(text)
        self.assertEqual(data.get("registration_date"), "2020-07-17")

    def test_parse_mulkiya_front_reg_date_label(self) -> None:
        """Reg. Date label on Mulkiya front should extract the following date."""
        text = """
        Vehicle License
        Reg. Date
        17/07/2020
        Traffic Plate No
        12345
        """
        data = parse_mulkiya_front(text)
        self.assertEqual(data.get("registration_date"), "2020-07-17")

    def test_parse_mulkiya_front_reg_date_embedded(self) -> None:
        """Reg. Date with inline value should extract registration date."""
        text = "Reg. Date. 17/07/2020"
        data = parse_mulkiya_front(text)
        self.assertEqual(data.get("registration_date"), "2020-07-17")

    def test_parse_mulkiya_front_reg_date_adjacent(self) -> None:
        """Date placed next to Reg. Date on the same line should extract."""
        text = "Reg. Date 17/07/2020"
        data = parse_mulkiya_front(text)
        self.assertEqual(data.get("registration_date"), "2020-07-17")

    def test_parse_mulkiya_front_reg_date_grid_cell_value(self) -> None:
        """Reg. Date label with value in the right-hand grid cell should extract."""
        text = "Reg. Date 02/03/2024"
        data = parse_mulkiya_front(text)
        self.assertEqual(data.get("registration_date"), "2024-03-02")

    def test_parse_mulkiya_front_reg_date_value_before_label(self) -> None:
        """OCR that places the date before the label should still extract."""
        text = "02/03/2024 Reg. Date"
        data = parse_mulkiya_front(text)
        self.assertEqual(data.get("registration_date"), "2024-03-02")

    def test_registration_date_from_azure_layout_right_cell(self) -> None:
        """Azure line geometry should read the date cell to the right of Reg. Date."""
        layout = {
            "lines": [
                {
                    "content": "Reg. Date",
                    "box": {
                        "x_min": 1.0,
                        "x_max": 2.2,
                        "y_min": 4.0,
                        "y_max": 4.4,
                        "x_center": 1.6,
                        "y_center": 4.2,
                        "height": 0.4,
                    },
                },
                {
                    "content": "02/03/2024",
                    "box": {
                        "x_min": 2.4,
                        "x_max": 3.4,
                        "y_min": 4.0,
                        "y_max": 4.4,
                        "x_center": 2.9,
                        "y_center": 4.2,
                        "height": 0.4,
                    },
                },
            ],
            "words": [],
        }
        self.assertEqual(
            _registration_date_from_azure_layout(layout),
            "2024-03-02",
        )

    def test_reg_date_not_confused_with_expiry_date(self) -> None:
        """Registration date must come from Reg. Date, not Expiry Date."""
        text = """
        Vehicle License
        Reg. Date
        17/07/2020
        Expiry Date
        28/11/2038
        """
        data = parse_mulkiya_front(text)
        self.assertEqual(data.get("registration_date"), "2020-07-17")
        self.assertNotEqual(data.get("registration_date"), "2038-11-28")

    def test_reg_date_right_column_when_shared_values_row(self) -> None:
        """When Exp. Date and Reg. Date share a row, use the right-hand date."""
        text = """
        Vehicle License
        Exp. Date Reg. Date
        28/11/2038 17/07/2020
        """
        data = parse_mulkiya_front(text)
        self.assertEqual(data.get("registration_date"), "2020-07-17")

    def test_reg_date_left_column_when_reg_label_is_first(self) -> None:
        """When Reg. Date is left of Exp. Date, use the left-hand date."""
        text = """
        Reg. Date Exp. Date
        17/07/2020 28/11/2038
        """
        data = parse_mulkiya_front(text)
        self.assertEqual(data.get("registration_date"), "2020-07-17")

    def test_parse_mulkiya_front_registration_date_inline(self) -> None:
        """Inline registration date should be parsed without a following line."""
        text = "Reg. Date: 01-03-2019"
        data = parse_mulkiya_front(text)
        self.assertEqual(data.get("registration_date"), "2019-03-01")

    def test_parse_mulkiya_front_registration_date_from_azure_field(self) -> None:
        """Azure RegDate should map to registration_date (not generic RegistrationDate)."""
        data = parse_mulkiya_front(
            "",
            existing_fields={"RegDate": "17/07/2020"},
        )
        self.assertEqual(data.get("registration_date"), "2020-07-17")

    def test_parse_mulkiya_front_tcf_number(self) -> None:
        """T. C. No label on Mulkiya front should extract TCF number."""
        text = """
        Vehicle License
        T. C. No
        5080136781
        Traffic Plate No
        12345
        """
        data = parse_mulkiya_front(text)
        self.assertEqual(data.get("tcf_number"), "5080136781")

    def test_parse_mulkiya_front_tcf_number_inline(self) -> None:
        """Inline T. C. No value should extract TCF number."""
        text = "T. C. No: 343"
        data = parse_mulkiya_front(text)
        self.assertEqual(data.get("tcf_number"), "343")

    def test_parse_mulkiya_front_tcf_from_azure_field(self) -> None:
        """Azure tcf_number field should map to TCF number."""
        data = parse_mulkiya_front(
            "",
            existing_fields={"tcf_number": "5080136781"},
        )
        self.assertEqual(data.get("tcf_number"), "5080136781")

    def test_parse_mulkiya_front_plate_and_emirate(self) -> None:
        """Front side should extract traffic plate number and emirate."""
        text = """
        United Arab Emirates
        Vehicle License
        Traffic Plate No
        12345
        Plate Code
        A
        Dubai
        """
        data = parse_mulkiya_front(text)
        self.assertEqual(data.get("plate_code"), "A")
        self.assertEqual(data.get("plate_category"), "A")
        self.assertEqual(data.get("registration_no"), "12345")
        self.assertEqual(data.get("plate_source"), "DUBAI")

    def test_parse_mulkiya_front_traffic_plate_no_label(self) -> None:
        """Traffic Plate No. digits should populate registration_no, not plate_code."""
        text = """
        Vehicle License
        Traffic Plate No.
        5080136781
        """
        data = parse_mulkiya_front(text)
        self.assertEqual(data.get("registration_no"), "5080136781")
        self.assertNotEqual(data.get("plate_code"), "5080136781")

    def test_parse_mulkiya_front_traffic_plate_combined(self) -> None:
        """Traffic Plate No. should split category plate code and registration number."""
        text = "Traffic Plate No.: A 12345"
        data = parse_mulkiya_front(text)
        self.assertEqual(data.get("registration_no"), "12345")
        self.assertEqual(data.get("plate_category"), "A")
        self.assertEqual(data.get("plate_code"), "A")

    def test_traffic_plate_from_azure_layout_right_cells(self) -> None:
        """Azure geometry should read plate code and number cells beside the label."""
        layout = {
            "lines": [
                {
                    "content": "Traffic Plate No.",
                    "box": {
                        "x_min": 1.0,
                        "x_max": 2.5,
                        "y_min": 3.0,
                        "y_max": 3.4,
                        "x_center": 1.75,
                        "y_center": 3.2,
                        "height": 0.4,
                    },
                },
                {
                    "content": "A",
                    "box": {
                        "x_min": 2.6,
                        "x_max": 2.9,
                        "y_min": 3.0,
                        "y_max": 3.4,
                        "x_center": 2.75,
                        "y_center": 3.2,
                        "height": 0.4,
                    },
                },
                {
                    "content": "5080136781",
                    "box": {
                        "x_min": 3.0,
                        "x_max": 4.2,
                        "y_min": 3.0,
                        "y_max": 3.4,
                        "x_center": 3.6,
                        "y_center": 3.2,
                        "height": 0.4,
                    },
                },
            ],
            "words": [],
        }
        self.assertEqual(
            _traffic_plate_from_azure_layout(layout),
            {
                "plate_code": "A",
                "registration_no": "5080136781",
            },
        )

    def test_parse_mulkiya_front_place_of_issue_english(self) -> None:
        """Place of Issue should populate plate_source in English."""
        text = """
        Vehicle License
        Place of Issue
        Abu Dhabi
        Traffic Plate No
        12345
        """
        data = parse_mulkiya_front(text)
        self.assertEqual(data.get("plate_source"), "ABU DHABI")

    def test_parse_mulkiya_front_place_of_issue_arabic(self) -> None:
        """Arabic Place of Issue should translate to English plate source."""
        text = """
        Vehicle License
        Place of Issue
        دبي
        Traffic Plate No
        12345
        """
        data = parse_mulkiya_front(text)
        self.assertEqual(data.get("plate_source"), "DUBAI")

    def test_parse_mulkiya_front_place_of_issue_inline_arabic(self) -> None:
        """Inline Arabic place of issue should translate to English."""
        text = "Place of Issue: الشارقة"
        data = parse_mulkiya_front(text)
        self.assertEqual(data.get("plate_source"), "SHARJAH")

    def test_parse_mulkiya_front_place_of_issue_from_azure_field(self) -> None:
        """Azure PlaceOfIssue should map to plate_source."""
        data = parse_mulkiya_front(
            "",
            existing_fields={"PlaceOfIssue": "رأس الخيمة"},
        )
        self.assertEqual(data.get("plate_source"), "RAS AL KHAIMAH")

    def test_parse_mulkiya_front_origin_arabic_field(self) -> None:
        """Azure origin with Arabic emirate should translate to English."""
        data = parse_mulkiya_front(
            "",
            existing_fields={"origin": "إمارة دبي"},
        )
        self.assertEqual(data.get("plate_source"), "DUBAI")

    def test_normalize_plate_source_never_returns_arabic(self) -> None:
        """Unknown Arabic text should not be returned as plate source."""
        from apps.ocr.plate_utils import normalize_plate_source

        self.assertEqual(normalize_plate_source("دبي"), "DUBAI")
        self.assertEqual(normalize_plate_source("نص غير معروف"), "")

    def test_parse_mulkiya_back_chassis(self) -> None:
        """Back side should extract 17-character chassis/VIN."""
        text = """
        Vehicle Information
        Chassis No
        JMZBK14F251234567
        """
        data = parse_mulkiya_back(text)
        self.assertEqual(data.get("chassis_no"), "JMZBK14F251234567")

    def test_parse_mulkiya_back_model(self) -> None:
        """Back side should extract vehicle model from the Model label."""
        text = """
        Vehicle Information
        Model
        OUTLANDER
        Chassis No
        JMZBK14F251234567
        """
        data = parse_mulkiya_back(text)
        self.assertEqual(data.get("model_id"), "OUTLANDER")

    def test_parse_mulkiya_back_model_year_on_next_line(self) -> None:
        """Model year on the line after model name should be extracted."""
        text = """
        Vehicle Information
        Model
        OUTLANDER
        2022
        Chassis No
        JMZBK14F251234567
        """
        data = parse_mulkiya_back(text)
        self.assertEqual(data.get("model_id"), "OUTLANDER")
        self.assertEqual(data.get("model_year"), "2022")

    def test_parse_mulkiya_back_model_year_inline(self) -> None:
        """Inline model and year on the Model label line should both be parsed."""
        text = "Model: OUTLANDER 2022"
        data = parse_mulkiya_back(text)
        self.assertEqual(data.get("model_id"), "OUTLANDER")
        self.assertEqual(data.get("model_year"), "2022")

    def test_parse_mulkiya_back_model_year_from_azure_model_field(self) -> None:
        """Azure Model value with embedded year should populate model_year."""
        data = parse_mulkiya_back(
            "",
            existing_fields={"Model": "OUTLANDER 2022"},
        )
        self.assertEqual(data.get("model_id"), "OUTLANDER")
        self.assertEqual(data.get("model_year"), "2022")

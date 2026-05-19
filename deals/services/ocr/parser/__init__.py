"""Document-specific OCR parsers."""

from deals.services.ocr.parser.driving_license import parse_driving_license
from deals.services.ocr.parser.emirates_id import parse_emirates_id
from deals.services.ocr.parser.mulkiya_parser import parse_mulkiya

__all__ = ["parse_driving_license", "parse_emirates_id", "parse_mulkiya"]

"""Map structured parser output to CRM / deal_create field names."""

from deals.services.ocr.mapper.deal_create_mapper import map_parser_result_to_deal_create

__all__ = ["map_parser_result_to_deal_create"]

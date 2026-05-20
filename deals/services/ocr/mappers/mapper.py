from .mulkiya_mapper import map_mulkiya_to_form
from .emirates_id_mapper import map_emirates_id_to_form
from .driving_license_mapper import map_driving_license_to_form


MULKIYA_TYPES = frozenset(
    {"mulkiya", "mulkiya_front", "mulkiya_back", "mulkiya_id_front", "mulkiya_id_back"}
)
EMIRATES_ID_TYPES = frozenset(
    {"emirates_id", "emirates_id_front", "emirates_id_back"}
)
DRIVING_LICENSE_TYPES = frozenset(
    {"driving_license", "driving_license_front", "driving_license_back"}
)


def map_document_to_form(parsed_data):
    document_type = (parsed_data.get("document_type") or "").lower()

    if document_type in MULKIYA_TYPES:
        return map_mulkiya_to_form(parsed_data)

    if document_type in EMIRATES_ID_TYPES:
        return map_emirates_id_to_form(parsed_data)

    if document_type in DRIVING_LICENSE_TYPES:
        return map_driving_license_to_form(parsed_data)

    return {
        "document_type": document_type or "unknown",
        "error": "No mapper found for document type"
    }
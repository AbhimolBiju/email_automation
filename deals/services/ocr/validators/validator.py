from .emirates_id_validator import validate_emirates_id
from .driving_license_validator import validate_driving_license
from .mulkiya_validator import validate_mulkiya


MULKIYA_TYPES = frozenset(
    {"mulkiya", "mulkiya_front", "mulkiya_back", "mulkiya_id_front", "mulkiya_id_back"}
)
EMIRATES_ID_TYPES = frozenset(
    {"emirates_id", "emirates_id_front", "emirates_id_back"}
)
DRIVING_LICENSE_TYPES = frozenset(
    {"driving_license", "driving_license_front", "driving_license_back"}
)


def validate_document(parsed_data):
    document_type = (parsed_data.get("document_type") or "").lower()

    if document_type in EMIRATES_ID_TYPES:
        return validate_emirates_id(parsed_data)

    if document_type in DRIVING_LICENSE_TYPES:
        return validate_driving_license(parsed_data)

    if document_type in MULKIYA_TYPES:
        return validate_mulkiya(parsed_data)

    return {
        "status": "PENDING",
        "errors": {
            "document_type": "Unsupported document type"
        },
        "side": "unknown"
    }
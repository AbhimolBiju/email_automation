from .mulkiya_parser import parse_mulkiya
from .emirates_id_parser import parse_emirates_id
from .driving_license_parser import parse_driving_license

MULKIYA_TYPES = frozenset(
    {"mulkiya", "mulkiya_front", "mulkiya_back", "mulkiya_id_front", "mulkiya_id_back"}
)
EMIRATES_ID_TYPES = frozenset(
    {"emirates_id", "emirates_id_front", "emirates_id_back"}
)
DRIVING_LICENSE_TYPES = frozenset(
    {"driving_license", "driving_license_front", "driving_license_back"}
)


def parse_document(text, document_type=None, key_values=None, tables=None, azure_json=None):
    document_type = (document_type or "").lower()

    if document_type in MULKIYA_TYPES:
        return parse_mulkiya(
            text=text,
            key_values=key_values
        )

    if document_type in EMIRATES_ID_TYPES:
        return parse_emirates_id(
            text=text,
            document_type=document_type,
            key_values=key_values,
            tables=tables
        )

    if document_type in DRIVING_LICENSE_TYPES:
        return parse_driving_license(
            text=text,
            document_type=document_type,
            key_values=key_values,
            tables=tables,
            azure_json=azure_json
        )

    return {
        "document_type": document_type or "unknown",
        "side": "unknown",
        "data": {},
        "values": {},
        "validation_errors": {
            "document_type": "Unsupported document type"
        },
        "confidence": {}
    }


# def parse_document(text, document_type=None,key_values=None,tables=None):

#     if document_type in ["mulkiya", "mulkiya_front", "mulkiya_back"]:

#         return parse_mulkiya(text,key_values=key_values)

#     return {
#         "document_type": document_type or "unknown",
#         "mulkiya_side": "unknown",
#         "data": {},
#         "values": {}
#     }

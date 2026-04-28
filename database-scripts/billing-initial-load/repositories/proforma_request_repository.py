"""
Repositorio de acceso a la colección proformaRequests para billing-initial-load.

Colección: proformaRequests

Operaciones:
  - save: inserción de un nuevo proformaRequest asociado a una proforma creada
"""

import query_logger

COLLECTION_NAME = "proformaRequests"


def save(collection, request_doc: dict) -> None:
    """
    Inserta un documento de proformaRequest.

    Args:
        collection:   Colección pymongo de proformaRequests.
        request_doc:  Documento construido con build_proforma_request().
    """
    query_logger.log_mongo(COLLECTION_NAME, "insert_one", {"requestId": request_doc.get("requestId")})
    collection.insert_one(request_doc)

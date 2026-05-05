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


def save_many(collection, request_docs: list) -> None:
    """
    Inserta múltiples proformaRequests en una sola operación.

    Args:
        collection:    Colección pymongo de proformaRequests.
        request_docs:  Lista de documentos construidos con build_proforma_request().
    """
    if not request_docs:
        return
    query_logger.log_mongo(COLLECTION_NAME, "insert_many", {"count": len(request_docs)})
    collection.insert_many(request_docs, ordered=False)

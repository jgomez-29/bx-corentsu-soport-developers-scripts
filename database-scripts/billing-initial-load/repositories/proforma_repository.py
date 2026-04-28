"""
Repositorio de acceso a la colección proformas para billing-initial-load.

Colección: proformas

Operaciones:
  - find_by_accounts:  búsqueda masiva por accounts para lookup in-memory (R-07)
  - save:              inserción de una nueva proforma legacy
"""

import query_logger

COLLECTION_NAME = "proformas"


def find_by_accounts(collection, accounts: list) -> list:
    """
    Retorna todas las proformas de las cuentas indicadas.

    Usado para construir el mapa in-memory (account, numeric_id) → proforma_doc
    que evita N consultas con $regex por OS del lote (R-07).

    Proyecta solo los campos necesarios para el lookup y para construir billing.

    Args:
        collection: Colección pymongo de proformas.
        accounts:   Lista de account strings (únicos del lote actual).

    Returns:
        Lista de documentos proforma con _id, account, proformaSerie, serviceCharges.
    """
    if not accounts:
        return []

    clean = [a for a in accounts if a]
    if not clean:
        return []

    projection = {
        "_id": 1,
        "account": 1,
        "proformaSerie": 1,
        "serviceCharges": 1,
    }
    query_logger.log_mongo(COLLECTION_NAME, "find", {"account": {"$in": clean}}, projection)
    return list(collection.find({"account": {"$in": clean}}, projection))


def save(collection, proforma_doc: dict) -> str:
    """
    Inserta una nueva proforma y retorna el _id hex string.

    Args:
        collection:   Colección pymongo de proformas.
        proforma_doc: Documento construido con build_proforma().

    Returns:
        Hex string del ObjectId insertado.
    """
    query_logger.log_mongo(COLLECTION_NAME, "insert_one", {"account": proforma_doc.get("account"), "proformaSerie": proforma_doc.get("proformaSerie")})
    result = collection.insert_one(proforma_doc)
    return str(result.inserted_id)

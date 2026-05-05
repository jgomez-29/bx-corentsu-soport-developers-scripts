"""
Repositorio de acceso a la colección invoices para billing-initial-load.

Colección: invoices

Operaciones:
  - find_existing_sii_folios:  verificación masiva de folios ya existentes
  - save_many:                 inserción bulk de nuevas invoices
"""

import query_logger

COLLECTION_NAME = "invoices"


def find_existing_sii_folios(collection, sii_folios: list, invoice_type: str = None) -> set:
    """
    Retorna el conjunto de siiFolios que ya existen en la colección.

    Usado para evitar duplicados al crear invoices dentro de un lote.

    Args:
        collection:   Colección pymongo de invoices.
        sii_folios:   Lista de siiFolios del lote actual.
        invoice_type: Si se especifica, filtra además por el campo 'type' del documento.

    Returns:
        Set de strings con los siiFolios ya presentes.
    """
    if not sii_folios:
        return set()

    clean = [f for f in sii_folios if f]
    if not clean:
        return set()

    query_filter = {"siiFolio": {"$in": clean}}
    if invoice_type is not None:
        query_filter["type"] = invoice_type

    query_logger.log_mongo(COLLECTION_NAME, "find", query_filter, {"siiFolio": 1, "_id": 0})
    docs = collection.find(query_filter, {"siiFolio": 1, "_id": 0})
    return {doc["siiFolio"] for doc in docs}


def save_many(collection, invoice_docs: list) -> int:
    """
    Inserta múltiples invoices en un solo round-trip.

    Usa ordered=False para maximizar throughput (un error no aborta el resto).

    Args:
        collection:   Colección pymongo de invoices.
        invoice_docs: Lista de documentos construidos con build_invoice().

    Returns:
        Cantidad de documentos insertados.
    """
    if not invoice_docs:
        return 0

    query_logger.log_mongo(COLLECTION_NAME, f"insert_many ({len(invoice_docs)} docs)")
    result = collection.insert_many(invoice_docs, ordered=False)
    return len(result.inserted_ids)

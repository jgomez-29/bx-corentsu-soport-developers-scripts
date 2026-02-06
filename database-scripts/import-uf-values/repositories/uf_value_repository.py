"""
Repository para la colección "uf-values".

Colección: uf-values

Documento:
    { "date": ISODate, "value": float }

Operaciones:
    - find_existing_dates: consulta qué fechas ya existen (para no duplicar)
    - bulk_insert: inserta múltiples documentos de una vez
"""

from datetime import datetime
from typing import List, Dict, Any, Set


# Nombre de la colección en MongoDB
COLLECTION_NAME = "uf-values"


def find_existing_dates(collection, dates: List[datetime]) -> Set[str]:
    """
    Consulta cuáles de las fechas dadas ya existen en la colección.

    Args:
        collection: Referencia a la colección "uf-values" de pymongo
        dates: Lista de fechas a verificar

    Returns:
        Set de fechas existentes como strings ISO (para comparación rápida)
    """
    if not dates:
        return set()

    cursor = collection.find(
        {"date": {"$in": dates}},
        {"_id": 0, "date": 1},
    )

    return {doc["date"].isoformat() for doc in cursor}


def bulk_insert(collection, documents: List[Dict[str, Any]]) -> int:
    """
    Inserta múltiples documentos en la colección usando bulk insert.

    Args:
        collection: Referencia a la colección "uf-values" de pymongo
        documents: Lista de documentos { date, value }

    Returns:
        Cantidad de documentos insertados
    """
    if not documents:
        return 0

    result = collection.insert_many(documents, ordered=False)
    return len(result.inserted_ids)

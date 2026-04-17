"""
Repositorio de órdenes de servicio — colección 'orders' en MongoDB.

Provee acceso a la colección para:
    - Leer OS no facturadas por rango de fechas (keyset pagination por _id).
    - Actualizar en bulk el campo billing de las OS encontradas en Oracle.

Keyset pagination:
    Las consultas usan sort("_id", ASC) + limit(batch_size).
    Para páginas siguientes se agrega {"_id": {"$gt": last_seen_id}}.
    Esto es O(log N) y estable, a diferencia de skip() que es O(N).
"""

from datetime import datetime
from pymongo.operations import UpdateOne

from entities.order import build_billing_update

COLLECTION_NAME = "orders"

# Proyección mínima para el proceso: solo campos necesarios.
_PROJECTION = {"_id": 1, "orderId": 1, "referenceOrder": 1, "emissionDate": 1, "billing": 1}


def find_unbilled_orders_batch(
    collection,
    date_from: datetime,
    date_to: datetime,
    batch_size: int,
    last_id=None,
) -> list:
    """
    Retorna hasta batch_size OS no facturadas en el rango [date_from, date_to).

    Ordena por _id ASC para paginación keyset. Para obtener la siguiente página,
    pasar el _id del último documento de la página anterior como last_id.

    Args:
        collection: Colección pymongo de 'orders'.
        date_from:  Inicio del rango (inclusive), datetime UTC.
        date_to:    Fin del rango (exclusivo), datetime UTC.
        batch_size: Máximo de documentos a retornar (recomendado: 1000).
        last_id:    ObjectId del último doc procesado; None para primera página.

    Returns:
        Lista de documentos. Lista vacía indica fin de la paginación.
    """
    query = {
        "emissionDate": {"$gte": date_from, "$lt": date_to},
        "billing.status": {"$ne": "BILLED"},
    }
    if last_id is not None:
        query["_id"] = {"$gt": last_id}

    return list(
        collection.find(query, _PROJECTION).sort("_id", 1).limit(batch_size)
    )


def bulk_update_billing(
    collection,
    updates: list,
    dry_run: bool,
) -> tuple:
    """
    Actualiza en bulk el billing de las OS que encontraron proforma en Oracle.

    Cada entrada en updates es un dict con:
        _id:         ObjectId del documento en MongoDB.
        proforma_id: Valor de DCBT_NMR_FAC_PF a asignar en billing.proformaId.

    El filtro de cada UpdateOne incluye "billing.status": {"$ne": "BILLED"}
    como guardia de idempotencia: si la OS ya fue marcada por otra ejecución
    concurrente, la operación simplemente no aplica.

    Args:
        collection: Colección pymongo de 'orders'.
        updates:    Lista de dicts {_id, proforma_id}.
        dry_run:    Si True, no ejecuta la escritura en MongoDB.

    Returns:
        Tupla (updated_count, error_count).
    """
    if not updates:
        return 0, 0

    if dry_run:
        return len(updates), 0

    operations = [
        UpdateOne(
            filter={"_id": u["_id"], "billing.status": {"$ne": "BILLED"}},
            update={"$set": build_billing_update(u["proforma_id"])},
        )
        for u in updates
    ]

    try:
        result = collection.bulk_write(operations, ordered=False)
        return result.modified_count, 0
    except Exception as e:
        return 0, len(updates)

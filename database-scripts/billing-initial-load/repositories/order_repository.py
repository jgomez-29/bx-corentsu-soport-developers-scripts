"""
Repositorio de acceso a la colección orders para billing-initial-load.

Colección: orders

Operaciones:
  - get_orders_cursor:   cursor paginado por emissionDate para OS candidatas
  - bulk_write_billing:  actualización masiva del subdocumento billing
"""

from datetime import datetime
from pymongo import UpdateOne

import query_logger

COLLECTION_NAME = "orders"


def get_orders_cursor(collection, start_dt: datetime, end_dt: datetime, batch_size: int = 1000):
    """
    Retorna un cursor de OS candidatas para el rango [start_dt, end_dt).

    Filtros aplicados:
      - emissionDate >= start_dt y < end_dt  (usa el índice emissionDate)
      - taxDocument presente y no nulo
      - billing.status != "BILLED" (incluye OS sin campo billing)

    Proyección mínima para reducir transferencia de datos.

    Args:
        collection: Colección pymongo de orders.
        start_dt:   Inicio del intervalo (inclusive), datetime UTC.
        end_dt:     Fin del intervalo (exclusive), datetime UTC.
        batch_size: Tamaño del lote de red con MongoDB.
    """
    query = {
        "emissionDate": {"$gte": start_dt, "$lt": end_dt},
        "taxDocument": {"$exists": True, "$ne": None},
        "billing.status": {"$ne": "BILLED"},
    }
    projection = {
        "orderId": 1,
        "emissionDate": 1,
        "referenceOrder": 1,
        "seller.account": 1,
        "taxDocument": 1,
        "billing": 1,
    }
    query_logger.log_mongo(COLLECTION_NAME, "find", query, projection)
    return collection.find(query, projection, batch_size=batch_size)


def get_orders_cursor_legacy(
    collection,
    start_dt: datetime,
    end_dt: datetime,
    accounts: list,
    batch_size: int = 1000,
):
    """
    Retorna un cursor de OS candidatas para el modo legacy.

    A diferencia de get_orders_cursor, no filtra por taxDocument: en el modo
    legacy la fuente de verdad para las facturas es Oracle, no el campo taxDocument.

    Filtros aplicados:
      - emissionDate >= start_dt y < end_dt
      - billing.status != "BILLED" (incluye OS sin campo billing)
      - seller.account en la lista de cuentas del archivo configurado

    Args:
        collection: Colección pymongo de orders.
        start_dt:   Inicio del intervalo (inclusive), datetime UTC.
        end_dt:     Fin del intervalo (exclusive), datetime UTC.
        accounts:   Lista de accounts a filtrar.
        batch_size: Tamaño del lote de red con MongoDB.
    """
    query = {
        "emissionDate": {"$gte": start_dt, "$lt": end_dt},
        "billing.status": {"$ne": "BILLED"},
        "seller.account": {"$in": accounts},
    }
    projection = {
        "orderId": 1,
        "emissionDate": 1,
        "referenceOrder": 1,
        "seller.account": 1,
        "billing": 1,
    }
    query_logger.log_mongo(COLLECTION_NAME, "find", query, projection)
    return collection.find(query, projection, batch_size=batch_size).hint([
        ("seller.account", 1),
        ("emissionDate", 1),
        ("billing.deliveryDate", 1),
        ("billing.proformaId", 1),
        ("state", 1),
        ("_id", 1),
    ])


def bulk_write_billing(collection, updates: list) -> dict:
    """
    Actualiza el subdocumento billing de múltiples órdenes en un solo round-trip.

    Usa $set por campo individual para preservar campos existentes en billing
    (documentType, deliveryDate, serviceCharges) que no gestionamos aquí.

    Args:
        collection: Colección pymongo de orders.
        updates:    Lista de dicts con {orderId: str, billing: dict}.

    Returns:
        Dict con claves 'matched' y 'modified'.
    """
    if not updates:
        return {"matched": 0, "modified": 0}

    operations = []
    for upd in updates:
        order_id = upd["orderId"]
        billing = upd["billing"]

        set_doc = {}
        for key, value in billing.items():
            if isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    set_doc[f"billing.{key}.{sub_key}"] = sub_value
            else:
                set_doc[f"billing.{key}"] = value

        operations.append(UpdateOne({"orderId": order_id}, {"$set": set_doc}))

    query_logger.log_mongo(COLLECTION_NAME, f"bulk_write ({len(updates)} ops)", {"orderId": "$in [batch]"})
    result = collection.bulk_write(operations, ordered=False)
    return {"matched": result.matched_count, "modified": result.modified_count}

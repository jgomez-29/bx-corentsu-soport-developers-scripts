"""
Repository para la colección "orders".

Base de datos: soport-orders
Colección: orders

Campos que leemos:
    - orderId          (str)  → Identificador único de la orden
    - billing.siiFolio (str)  → Folio SII asociado a la orden (dentro del subdocumento billing)
    - buyer.email      (str)  → Email del comprador (destinatario real de la notificación)

Filtro de búsqueda:
    { "orderId": <orderId> }

Ejemplo de documento relevante en MongoDB:
    {
        "orderId": "8071056243",
        "buyer": {
            "email": "usuario@ejemplo.com",
            ...
        },
        "billing": {
            "siiFolio": "2100",
            "proformaId": "69388e8f4ea80628df7c5d6c",
            "proformaSerie": "PRO_SCJS_202512_1119408",
            "status": "BILLED",
            ...
        },
        ...
    }
"""

from typing import Optional, Dict, Any


# Nombre de la colección en MongoDB
COLLECTION_NAME = "orders"

# Campos que proyectamos (solo lo que necesitamos)
ORDER_PROJECTION = {
    "_id": 0,
    "orderId": 1,
    "buyer.email": 1,
    "billing.siiFolio": 1,
}


def find_order_by_order_id(collection, order_id: str) -> Optional[Dict[str, Any]]:
    """
    Busca una orden por orderId y retorna solo los campos necesarios.

    Args:
        collection: Referencia a la colección "orders" de pymongo
        order_id: Identificador de la orden

    Returns:
        Diccionario con {orderId, buyer: {email}, billing: {siiFolio}} o None si no existe
    """
    return collection.find_one(
        {"orderId": order_id},
        ORDER_PROJECTION,
    )


def extract_sii_folio(order: Dict[str, Any]) -> Optional[str]:
    """
    Extrae el siiFolio del subdocumento billing de una orden.

    Args:
        order: Documento de orden retornado por find_order_by_order_id

    Returns:
        El siiFolio como string o None si no existe
    """
    billing = order.get("billing")
    if not billing:
        return None
    return billing.get("siiFolio")


def extract_buyer_email(order: Dict[str, Any]) -> Optional[str]:
    """
    Extrae el email del comprador (buyer.email).

    Args:
        order: Documento de orden retornado por find_order_by_order_id

    Returns:
        Email del comprador o None si no existe
    """
    buyer = order.get("buyer")
    if not buyer:
        return None
    return buyer.get("email")

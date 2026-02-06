"""
Repository para la colección "invoices".

Base de datos: soport-orders
Colección: invoices

Campos que leemos:
    - siiFolio                       (str)   → Folio SII del documento
    - siiDocumentPath                (str)   → URL del documento SII (enlace al comprobante)
    - totalDetail.totalToPay         (int)   → Monto total a pagar
    - relatedElements[].identifier   (str)   → Identificador de la orden relacionada
    - relatedElements[].type         (str)   → Tipo del elemento relacionado ("order")

Filtro de búsqueda:
    { "siiFolio": <siiFolio>, "relatedElements.identifier": <orderId> }

Ejemplo de documento relevante en MongoDB:
    {
        "siiFolio": "5612820",
        "siiDocumentPath": "http://windte2602.acepta.com/ca4webv3/PdfView?url=...",
        "totalDetail": {
            "totalToPay": 3990,
            ...
        },
        "relatedElements": [
            {
                "identifier": "1003939941",
                "type": "order"
            }
        ],
        ...
    }
"""

from typing import Optional, Dict, Any


# Nombre de la colección en MongoDB
COLLECTION_NAME = "invoices"

# Campos que proyectamos (solo lo que necesitamos)
INVOICE_PROJECTION = {
    "_id": 0,
    "siiFolio": 1,
    "siiDocumentPath": 1,
    "totalDetail.totalToPay": 1,
    "relatedElements": 1,
}


def find_invoice_by_folio_and_order(
    collection,
    sii_folio: str,
    order_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Busca una factura por siiFolio y orderId en relatedElements.

    Args:
        collection: Referencia a la colección "invoices" de pymongo
        sii_folio: Folio SII del documento
        order_id: Identificador de la orden relacionada

    Returns:
        Diccionario con los campos proyectados o None si no existe
    """
    return collection.find_one(
        {
            "siiFolio": sii_folio,
            "relatedElements.identifier": order_id,
        },
        INVOICE_PROJECTION,
    )


def extract_document_path(invoice: Dict[str, Any]) -> Optional[str]:
    """
    Extrae la URL del documento SII (enlace al comprobante).

    Args:
        invoice: Documento de factura retornado por find_invoice_by_folio_and_order

    Returns:
        URL del documento o None
    """
    return invoice.get("siiDocumentPath")


def extract_total_to_pay(invoice: Dict[str, Any]) -> Optional[int]:
    """
    Extrae el monto total a pagar.

    Args:
        invoice: Documento de factura retornado por find_invoice_by_folio_and_order

    Returns:
        Monto total o None
    """
    total_detail = invoice.get("totalDetail")
    if not total_detail:
        return None
    return total_detail.get("totalToPay")

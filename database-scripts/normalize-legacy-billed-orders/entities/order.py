"""
Entidad: Orden de Servicio (OS) — colección 'orders' en MongoDB.

Estructura del documento relevante para este script:
    {
        "_id": ObjectId,                  # ID interno MongoDB (keyset pagination)
        "orderId": str,                   # ID de la orden en el nuevo core
        "referenceOrder": str,            # ID en sistema legado (= EEVV_NMR_ID en Oracle)
        "emissionDate": datetime (UTC),   # Fecha de emisión de la OS
        "billing": {                      # Puede ser null o no existir
            "status": str | None,         # "BILLED" si ya fue facturada
            "proformaId": str | None,     # Número de proforma legado (DCBT_NMR_FAC_PF)
            "siiFolio": str | None,       # Folio SII (completado por consumer, no este script)
            "proformaSerie": str | None,  # Serie de proforma (completado por consumer)
            "billingDate": datetime | None  # Fecha de facturación (completado por consumer)
        }
    }

Ejemplo:
    {
        "_id": ObjectId("67f1a2b3c4d5e6f7a8b9c0d1"),
        "orderId": "ORD-2026-001234",
        "referenceOrder": "REF-00098765",
        "emissionDate": ISODate("2026-01-15T00:00:00.000Z"),
        "billing": null
    }

Colección: orders
"""


def build_billing_update(proforma_id: str) -> dict:
    """
    Construye el dict de $set para marcar una OS como BILLED en la carga inicial.

    Solo asigna proformaId y status. Los demás campos del objeto billing
    (siiFolio, proformaSerie, billingDate) se preservan intactos y serán
    completados por el consumer orders-consolidation cuando corresponda.

    Args:
        proforma_id: Valor de DCBT_NMR_FAC_PF obtenido desde Oracle.

    Returns:
        Dict listo para usar en $set de una operación UpdateOne de MongoDB.
    """
    return {
        "billing.proformaId": proforma_id,
        "billing.status": "BILLED",
    }

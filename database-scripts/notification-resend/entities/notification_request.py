"""
Estructura del request para la API de envío de notificaciones.

API:
    POST {BASE_URL}/notif/on-demand/v1/ses

Headers:
    X-Team-Domain: Domain
    X-Team-Subdomain: Subdomain
    X-Team-Capability: Capability
    Content-Type: application/json

Body:
    {
        "templateName": "billing-core-order-biling-mail",
        "fromAddress": "noreply@blue.cl",
        "recipient": {
            "to": ["<email>"],
            "cc": [],
            "bcc": []
        },
        "templateData": [
            { "key": "serviceOrderNumber", "value": "<orderId>" },
            { "key": "enlace_comprobante", "value": "<siiDocumentPath>" },
            { "key": "monto", "value": "<totalToPay>" }
        ]
    }

Mapeo de campos:
    - serviceOrderNumber  ← orders.orderId (CSV #identifier)
    - enlace_comprobante  ← invoices.siiDocumentPath
    - monto               ← invoices.totalDetail.totalToPay
    - recipient.to        ← configurado en config.py (correo destino)
"""

from typing import List, Dict, Any


def build_notification_request(
    order_id: str,
    sii_document_path: str,
    total_to_pay: int,
    recipient_email: str,
    template_name: str = "billing-core-order-biling-mail",
    from_address: str = "noreply@blue.cl",
) -> Dict[str, Any]:
    """
    Construye el payload para la API de envío de notificaciones.

    Args:
        order_id: Número de orden (serviceOrderNumber)
        sii_document_path: URL del comprobante (enlace_comprobante)
        total_to_pay: Monto total a pagar
        recipient_email: Email del destinatario
        template_name: Nombre del template de correo
        from_address: Dirección de envío

    Returns:
        Diccionario con la estructura del request
    """
    return {
        "templateName": template_name,
        "fromAddress": from_address,
        "recipient": {
            "to": [recipient_email],
            "cc": [],
            "bcc": [],
        },
        "templateData": [
            {
                "key": "serviceOrderNumber",
                "value": str(order_id),
            },
            {
                "key": "enlace_comprobante",
                "value": str(sii_document_path),
            },
            {
                "key": "monto",
                "value": str(total_to_pay),
            },
        ],
    }


# Headers requeridos por la API
NOTIFICATION_HEADERS = {
    "X-Team-Domain": "Domain",
    "X-Team-Subdomain": "Subdomain",
    "X-Team-Capability": "Capability",
    "Content-Type": "application/json",
}

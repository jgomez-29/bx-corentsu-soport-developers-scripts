"""
Módulo para construir mensajes DteInformation (MessageSQS) para la cola biller-unitary.

Genera payloads válidos para pruebas de estrés: el consumer espera el cuerpo del mensaje
como JSON de MessageSQS con Message (string = JSON de DteInformation) y MessageAttributes
(channel, eventType) obligatorios.

Puede usar una plantilla JSON por ambiente (dev/entities/dte-information.json o
qa/entities/dte-information.json) o generar payloads sintéticos.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

# Valores por defecto para MessageAttributes (alineados con Helm biller-unitary)
DEFAULT_CHANNEL = "WEB"
DEFAULT_EVENT_TYPE = "billingOrchestrated"


def build_dte_information_payload(identifier: str, index: int) -> Dict[str, Any]:
    """
    Construye un DteInformation mínimo válido para el consumer biller-unitary.

    Args:
        identifier: Identificador único del mensaje (p.ej. order-123).
        index: Índice del mensaje (para variar montos si se desea).

    Returns:
        Dict que representa DteInformation (billing, details, totalDetail coherentes).
    """
    unitary_value = 100.0 + (index % 100)
    quantity = 1
    total_value = round(unitary_value * quantity, 2)
    taxable_sub_total = total_value
    tax = round(taxable_sub_total * 0.19, 2)
    total = round(taxable_sub_total + tax, 2)
    cash_adjustment = 0.0
    total_to_pay = round(total + cash_adjustment, 2)

    return {
        "identifier": identifier,
        "identifierType": "order",
        "account": "stress-test-account",
        "createBy": "stress-script",
        "society": "1700",
        "billing": {
            "documentType": "33",
            "transaction": {
                "paymentMethod": "CONTADO",
                "transactionId": f"tx-{identifier}",
                "paymentType": "1",
                "collector": "stress-script",
            },
            "rut": "12345678-9",
            "name": "Cliente Prueba Estrés",
            "giro": "Giro prueba",
            "address": "Av Test 100",
            "city": "Santiago",
            "commune": "Santiago",
            "sellCondition": "Contado",
            "phone": "+56912345678",
            "email": "test@test.local",
        },
        "details": [
            {
                "description": f"Item estrés {index}",
                "unitaryValue": unitary_value,
                "totalValue": total_value,
                "quantity": quantity,
                "isExempt": False,
                "isDiscount": False,
            }
        ],
        "attachments": [],
        "totalDetail": {
            "cashAdjustment": cash_adjustment,
            "exemptSubtotal": 0.0,
            "taxableSubTotal": taxable_sub_total,
            "tax": tax,
            "total": total,
            "totalToPay": total_to_pay,
            "discount": 0.0,
        },
    }


def load_entity_template(file_path: str) -> Optional[Dict[str, Any]]:
    """
    Carga una plantilla DteInformation desde un archivo JSON.

    Args:
        file_path: Ruta al archivo (dev/entities/dte-information.json o qa/...).

    Returns:
        Dict DteInformation o None si el archivo no existe.
    """
    path = Path(file_path)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_payloads_from_template(template: Dict[str, Any], n: int) -> List[Dict[str, Any]]:
    """
    Replica la plantilla n veces sin modificar identifier ni transactionId.

    Se respetan los valores originales de la plantilla para no causar errores
    en el consumer (p. ej. órdenes/documentos ya existentes).

    Args:
        template: Un DteInformation (dict) de referencia.
        n: Número de mensajes a generar.

    Returns:
        Lista de n copias del template (mismo identifier y transactionId en todas).
    """
    import copy
    return [copy.deepcopy(template) for _ in range(n)]


def generate_payloads(n: int) -> List[Dict[str, Any]]:
    """
    Genera n payloads (DteInformation) con identificadores únicos para pruebas de estrés.

    Args:
        n: Número de mensajes a generar.

    Returns:
        Lista de dicts, cada uno un DteInformation válido.
    """
    prefix = f"stress-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"
    return [
        build_dte_information_payload(f"{prefix}-{i}-{uuid.uuid4().hex[:8]}", i)
        for i in range(n)
    ]


def envelope_builder(
    payload: Dict[str, Any],
    channel: str = DEFAULT_CHANNEL,
    event_type: str = DEFAULT_EVENT_TYPE,
) -> Dict[str, Any]:
    """
    Construye el cuerpo del mensaje SQS en formato compatible con SNS→SQS.

    Incluye Type, MessageId, Message (JSON string DteInformation), Timestamp y
    MessageAttributes alineados con una notificación SNS (channel, eventType, entityType,
    entityId, traceId, eventId, version, datetime, domain, subdomain, businessCapability).

    Args:
        payload: Dict DteInformation (el payload interno).
        channel: Valor del atributo channel (default WEB).
        event_type: Valor del atributo eventType (default billingOrchestrated).

    Returns:
        Dict que se serializa a JSON y se envía como MessageBody a SQS.
    """
    now = datetime.now(timezone.utc)
    msg_id = str(uuid.uuid4())
    trace_id = uuid.uuid4().hex
    span_id = uuid.uuid4().hex[:16]
    entity_id = str(payload.get("identifier", ""))

    def attr_str(value: str) -> Dict[str, str]:
        return {"Type": "String", "Value": value}

    def attr_num(value: int) -> Dict[str, str]:
        return {"Type": "Number", "Value": str(value)}

    return {
        "Type": "Notification",
        "MessageId": msg_id,
        "Message": json.dumps(payload, ensure_ascii=False),
        "Timestamp": now.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "MessageAttributes": {
            "traceId": attr_str(trace_id),
            "eventId": attr_str(msg_id),
            "entityType": attr_str("BillingDocument"),
            "channel": attr_str(channel),
            "entityId": attr_str(entity_id),
            "eventType": attr_str(event_type),
            "version": attr_str("1.0"),
            "spanId": attr_str(span_id),
            "datetime": attr_str(now.isoformat(timespec="milliseconds").replace("+00:00", "Z")),
            "domain": attr_str("corentsu"),
            "subdomain": attr_str("soport"),
            "businessCapability": attr_str("finmg"),
            "timestamp": attr_num(int(now.timestamp())),
        },
    }

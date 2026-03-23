"""
Módulo para construir mensajes CheckpointEvent (MessageSQS) para la cola proforma-checkpoints.

Genera payloads válidos para pruebas de carga: el consumer bx-cnsr-finmg-proforma-checkpoints
espera el cuerpo del mensaje como JSON de MessageSQS con Message (string = JSON de
CheckpointEvent) y MessageAttributes (channel, eventType, domain, subdomain,
businessCapability, etc.) incluidos por consistencia.

Estrategia de orderId fijo:
  Todos los mensajes (sintéticos o de plantilla) comparten el mismo orderId. Esto
  garantiza que la prueba golpee siempre el mismo documento en Mongo y al terminar
  solo haya un registro de prueba que limpiar.

Puede usar una plantilla JSON por ambiente (dev/entities/checkpoint-event.json o
qa/entities/checkpoint-event.json) o generar payloads sintéticos.
"""

import copy
import json
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

# Códigos de evento válidos para CheckpointEvent (ciclan en orden)
VALID_EVENT_CODES = ["DL", "DLV", "DLO", "LD", "MST", "PM", "PDP", "VP", "DM"]

# Valor por defecto del atributo channel para MessageAttributes
DEFAULT_CHANNEL = "Legacy"


def build_checkpoint_event_payload(order_id: str, index: int) -> Dict[str, Any]:
    """
    Construye un CheckpointEvent válido para el consumer proforma-checkpoints.

    orderId es fijo (el pasado como argumento) en todos los mensajes para que la
    prueba siempre opere sobre el mismo documento; packageId, trackingId y eventCode
    varían por índice.

    Args:
        order_id: Identificador de la orden (fijo en toda la prueba).
        index: Índice del mensaje (varía packageId, trackingId y eventCode).

    Returns:
        Dict que representa un CheckpointEvent.
    """
    event_code = VALID_EVENT_CODES[index % len(VALID_EVENT_CODES)]
    now = datetime.now(timezone.utc)
    event_date = (
        (now - timedelta(minutes=index))
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )
    creation_date = now.isoformat(timespec="milliseconds").replace("+00:00", "Z")

    return {
        "orderId": order_id,
        "sellerAccount": "stress-test-seller",
        "owner": "stress-test-owner",
        "packageId": f"pkg-{index:04d}",
        "trackingId": 1000 + index,
        "eventDate": event_date,
        "eventType": "created or modified",
        "eventCode": event_code,
        "location": "Santiago, Chile",
        "status": "ACTIVE",
        "agencyId": (index % 5) + 1,
        "geolocation": {
            "coordinates": [-33.4489 + (index * 0.001), -70.6693 + (index * 0.001)]
        },
        "creationDate": creation_date,
    }


def load_entity_template(file_path: str) -> Optional[Dict[str, Any]]:
    """
    Carga una plantilla CheckpointEvent desde un archivo JSON.

    Args:
        file_path: Ruta al archivo (dev/entities/checkpoint-event.json o qa/...).

    Returns:
        Dict CheckpointEvent o None si el archivo no existe.
    """
    path = Path(file_path)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_payloads_from_template(
    template: Dict[str, Any], n: int
) -> List[Dict[str, Any]]:
    """
    Replica la plantilla n veces manteniendo el mismo orderId en todas las copias.

    Todos los mensajes llevan el orderId original de la plantilla para que al
    terminar solo quede un documento de prueba en Mongo que limpiar.

    Args:
        template: Un CheckpointEvent (dict) de referencia.
        n: Número de mensajes a generar.

    Returns:
        Lista de n copias del template (mismo orderId en todas).
    """
    return [copy.deepcopy(template) for _ in range(n)]


def generate_payloads(n: int, order_id: str) -> List[Dict[str, Any]]:
    """
    Genera n payloads (CheckpointEvent) con el mismo orderId fijo para pruebas de carga.

    eventCode cicla, trackingId y packageId varían por índice.

    Args:
        n: Número de mensajes a generar.
        order_id: orderId fijo para todos los mensajes (p.ej. ORDER_ID de config.py).

    Returns:
        Lista de dicts, cada uno un CheckpointEvent válido con el mismo orderId.
    """
    return [build_checkpoint_event_payload(order_id, i) for i in range(n)]


def envelope_builder(
    payload: Dict[str, Any],
    channel: str = DEFAULT_CHANNEL,
    event_type: str = "created or modified",
) -> Dict[str, Any]:
    """
    Construye el cuerpo del mensaje SQS compatible con SNS→SQS (MessageSQS).

    El campo Message es el JSON string del CheckpointEvent. MessageAttributes incluidos
    por consistencia con el resto de consumers del ecosistema.

    Args:
        payload: Dict CheckpointEvent (el payload interno).
        channel: Valor del atributo channel (default Legacy).
        event_type: Valor del atributo eventType.

    Returns:
        Dict serializable a JSON que se envía como MessageBody a SQS.
    """
    now = datetime.now(timezone.utc)
    msg_id = str(uuid.uuid4())
    trace_id = uuid.uuid4().hex
    span_id = uuid.uuid4().hex[:16]

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
            "channel": attr_str(channel),
            "eventType": attr_str(event_type),
            "domain": attr_str("corentsu"),
            "subdomain": attr_str("soport"),
            "businessCapability": attr_str("finmg"),
            "spanId": attr_str(span_id),
            "datetime": attr_str(
                now.isoformat(timespec="milliseconds").replace("+00:00", "Z")
            ),
            "timestamp": attr_num(int(now.timestamp())),
        },
    }

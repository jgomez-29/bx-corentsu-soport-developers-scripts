"""
Builder de mensajes unitarios para payment process (eventType paymentProcessUnitary).

Genera payloads con requestId, origin, type, date, notificationEmail, documentToCreate.
El envelope incluye MessageAttributes: entityType, domain, channel, subdomain, entityId, eventType, version.
"""
import json
import random
import time
import uuid
import base64
from datetime import datetime
from typing import List, Dict, Any


def _generate_valid_rut() -> str:
    """Genera un RUT chileno válido (módulo 11)."""
    base = random.randint(1000000, 99999999)
    rut_str = str(base)
    mult = 2
    total = 0
    for d in reversed(rut_str):
        total += int(d) * mult
        mult = mult + 1 if mult < 7 else 2
    rem = total % 11
    dv = 11 - rem
    if dv == 11:
        dv_str = "0"
    elif dv == 10:
        dv_str = "K"
    else:
        dv_str = str(dv)
    return f"{base}-{dv_str}"


def _generate_unique_request_id() -> str:
    """Genera un requestId único (base64)."""
    ts = int(time.time() * 1000)
    uid = str(uuid.uuid4())
    combined = f"batch_{ts}_{uid}"
    return base64.b64encode(combined.encode()).decode()


def generate_payload(message_id: int) -> Dict[str, Any]:
    """
    Genera un payload unitario con la estructura esperada por paymentProcessUnitary.
    Regiones/comunas reducidas; el script original tiene el dataset completo.
    """
    regions = [
        {"regionCode": 13, "regionDesc": "REGION METROPOLITANA DE SANTIAGO"},
        {"regionCode": 5, "regionDesc": "REGION DE VALPARAISO"},
        {"regionCode": 1, "regionDesc": "REGION DE TARAPACA"},
    ]
    communes = [
        {"regionCode": 13, "comuneCode": 13101, "comuneDesc": "SANTIAGO"},
        {"regionCode": 13, "comuneCode": 13123, "comuneDesc": "PROVIDENCIA"},
        {"regionCode": 5, "comuneCode": 5301, "comuneDesc": "VALPARAISO"},
        {"regionCode": 1, "comuneCode": 1201, "comuneDesc": "IQUIQUE"},
    ]
    company_names = ["Proveedor Ejemplo S.A.", "Empresa Test Ltda.", "Comercial Demo S.A."]
    addresses = ["AVENIDA LIBERTADOR BERNARDO O'HIGGINS", "CALLE PRINCIPAL", "AVENIDA CENTRAL"]

    region = random.choice(regions)
    region_communes = [c for c in communes if c["regionCode"] == region["regionCode"]]
    commune = random.choice(region_communes) if region_communes else communes[0]

    return {
        "requestId": _generate_unique_request_id(),
        "origin": random.choice(["flex", "pudo"]),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "notificationEmail": "johann.gomez@blue.com",
        "type": "bte",
        "documentToCreate": {
            "providerIdentifier": _generate_valid_rut(),
            "providerName": random.choice(company_names),
            "regionName": region["regionDesc"],
            "comuneName": commune["comuneDesc"],
            "fullAddress": random.choice(addresses),
            "amount": 100,
            "frameworkAgreementCode": random.randint(100000, 999999),
            "HESCode": random.randint(10000, 99999),
            "BTECode": None,
            "billType": "Bol.Prest.Serv.Terce",
        },
    }


def generate_payloads(count: int) -> List[Dict[str, Any]]:
    """Genera una lista de count payloads unitarios."""
    return [generate_payload(i) for i in range(1, count + 1)]


def envelope_builder(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Construye el envelope para SNS: Message (body) y MessageAttributes.
    Compatible con common.sns.SNSPublisher.
    """
    message = json.dumps(payload, ensure_ascii=False)
    entity_id = payload.get("requestId", "")
    return {
        "Message": message,
        "MessageAttributes": {
            "entityType": {"DataType": "String", "StringValue": "PaymentDocument"},
            "domain": {"DataType": "String", "StringValue": "finmg"},
            "channel": {"DataType": "String", "StringValue": "api"},
            "subdomain": {"DataType": "String", "StringValue": "payment-process"},
            "entityId": {"DataType": "String", "StringValue": entity_id},
            "eventType": {"DataType": "String", "StringValue": "paymentProcessUnitary"},
            "version": {"DataType": "String", "StringValue": "1.0"},
        },
    }

"""
Builder de mensajes fragment para payment process (eventType paymentProcessRequested).

Genera payloads con bulkIdentifier, origin, date, notificationEmail, documentsToCreate (array).
El envelope incluye MessageAttributes: entityType PaymentProcess, eventType paymentProcessRequested, etc.
"""
import json
import random
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
    dv_str = "0" if dv == 11 else "K" if dv == 10 else str(dv)
    return f"{base}-{dv_str}"


def _generate_documents(num_documents: int = 2) -> List[Dict[str, Any]]:
    """Genera una lista de documentos (regiones/comunas reducidas)."""
    regions = [
        {"regionCode": 13, "regionDesc": "REGION METROPOLITANA DE SANTIAGO"},
        {"regionCode": 5, "regionDesc": "REGION DE VALPARAISO"},
    ]
    communes = [
        {"regionCode": 13, "comuneCode": 13101, "comuneDesc": "SANTIAGO"},
        {"regionCode": 13, "comuneCode": 13123, "comuneDesc": "PROVIDENCIA"},
        {"regionCode": 5, "comuneCode": 5301, "comuneDesc": "VALPARAISO"},
    ]
    company_names = ["Proveedor Ejemplo S.A.", "Empresa Test Ltda."]
    addresses = ["AVENIDA LIBERTADOR BERNARDO O'HIGGINS", "CALLE PRINCIPAL"]

    docs = []
    for _ in range(num_documents):
        region = random.choice(regions)
        region_communes = [c for c in communes if c["regionCode"] == region["regionCode"]]
        commune = random.choice(region_communes) if region_communes else communes[0]
        doc = {
            "providerIdentifier": _generate_valid_rut(),
            "providerName": random.choice(company_names),
            "regionName": region["regionDesc"],
            "comuneName": commune["comuneDesc"],
            "fullAddress": random.choice(addresses),
            "amount": random.choice([50, 100, 150, 200]),
        }
        if random.random() < 0.8:
            doc["frameworkAgreementCode"] = random.randint(100000, 999999)
        if random.random() < 0.7:
            doc["HESCode"] = random.randint(10000, 99999)
        docs.append(doc)
    return docs


def generate_payload(message_id: int, num_documents: int = 2) -> Dict[str, Any]:
    """Genera un payload fragment con documentsToCreate (array)."""
    return {
        "bulkIdentifier": f"batch-{datetime.now().strftime('%Y-%m-%d')}-{message_id}",
        "origin": "pudo",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "notificationEmail": "johann.gomez@blueexpress.cl",
        "documentsToCreate": _generate_documents(num_documents),
    }


def generate_payloads(count: int, num_documents_per_message: int = 2) -> List[Dict[str, Any]]:
    """Genera una lista de count payloads fragment."""
    return [generate_payload(i, num_documents_per_message) for i in range(1, count + 1)]


def envelope_builder(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Construye el envelope para SNS: Message y MessageAttributes.
    eventType: paymentProcessRequested.
    """
    import random
    message = json.dumps(payload, ensure_ascii=False)
    return {
        "Message": message,
        "MessageAttributes": {
            "traceId": {"DataType": "String", "StringValue": str(random.randint(1000000000000000000, 9999999999999999999))},
            "eventId": {"DataType": "String", "StringValue": f"{random.randint(10000000, 99999999)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}-{random.randint(100000000000, 999999999999)}"},
            "datetime": {"DataType": "String", "StringValue": datetime.now().isoformat() + "Z"},
            "entityType": {"DataType": "String", "StringValue": "PaymentProcess"},
            "domain": {"DataType": "String", "StringValue": "finmg"},
            "channel": {"DataType": "String", "StringValue": "payment-process"},
            "subdomain": {"DataType": "String", "StringValue": "payment-process"},
            "entityId": {"DataType": "String", "StringValue": "paymentProcessRequested"},
            "eventType": {"DataType": "String", "StringValue": "paymentProcessRequested"},
            "version": {"DataType": "String", "StringValue": "1.0"},
            "timestamp": {"DataType": "String", "StringValue": str(int(datetime.now().timestamp()))},
        },
    }

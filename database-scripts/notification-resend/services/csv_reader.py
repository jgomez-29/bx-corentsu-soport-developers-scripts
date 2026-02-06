"""
Servicio para leer fuentes de entrada de orderIds.

Soporta dos fuentes:
    1. CSV de errores de notificación (reports/notification-errors.csv)
    2. JSON de log de ejecución anterior (logs/resend_*.json) → para reintentar fallidos

CSV esperado:
    Separador: coma (,)
    Encoding: UTF-8
    Columnas: Date, Host, Service, #ordeId, #identifier, #recipient, Content
    Columnas que extraemos:
        - #identifier  → orderId
        - #recipient   → email original (para referencia)

JSON de retry esperado:
    El JSON generado por save_log() en run_resend.py.
    Contiene "results" con objetos que tienen "order_id" y "status".
    Se filtran solo los que NO tienen status "SENT".
"""

import csv
import json
from pathlib import Path
from typing import List, Dict


def read_notification_errors(csv_path: str) -> List[Dict[str, str]]:
    """
    Lee el CSV de errores de notificación y extrae los datos relevantes.

    Args:
        csv_path: Ruta al archivo CSV

    Returns:
        Lista de diccionarios con:
            - order_id: identificador de la orden (#identifier)
            - recipient: email original (#recipient)
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo CSV: {csv_path}")

    records = []

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            identifier = (row.get("#identifier") or "").strip()
            recipient = (row.get("#recipient") or "").strip()

            if not identifier:
                continue

            records.append({
                "order_id": identifier,
                "recipient": recipient,
            })

    return records


def get_unique_order_ids(records: List[Dict[str, str]]) -> List[str]:
    """
    Extrae los orderIds únicos de los registros del CSV.
    Mantiene el orden de primera aparición.

    Args:
        records: Lista de registros retornados por read_notification_errors

    Returns:
        Lista de orderIds únicos
    """
    seen = set()
    unique = []
    for record in records:
        oid = record["order_id"]
        if oid not in seen:
            seen.add(oid)
            unique.append(oid)
    return unique


def read_failed_from_log(json_path: str) -> List[str]:
    """
    Lee un JSON de log de ejecución anterior y extrae los orderIds
    que NO fueron enviados exitosamente (status != "SENT").

    Args:
        json_path: Ruta al archivo JSON de log

    Returns:
        Lista de orderIds fallidos (únicos, en orden)
    """
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo de log: {json_path}")

    with open(path, "r", encoding="utf-8") as f:
        log_data = json.load(f)

    results = log_data.get("results", [])
    if not results:
        raise ValueError(f"El archivo de log no contiene resultados: {json_path}")

    failed_ids = []
    seen = set()
    for entry in results:
        order_id = entry.get("order_id", "")
        status = entry.get("status", "")

        if status != "SENT" and order_id and order_id not in seen:
            seen.add(order_id)
            failed_ids.append(order_id)

    return failed_ids

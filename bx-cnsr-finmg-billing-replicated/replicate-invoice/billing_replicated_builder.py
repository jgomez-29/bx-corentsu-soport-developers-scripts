"""
Módulo para cargar y construir mensajes de replicación de facturas para SQS.

Carga los payloads de billing desde un archivo JSON y los prepara
para ser enviados a la cola queue-finmg-billing-replicated.
"""

import json
from pathlib import Path
from typing import List, Dict, Any


def load_billing_messages(input_file: str) -> List[Dict[str, Any]]:
    """
    Carga los mensajes de billing desde un archivo JSON.

    El archivo puede ser:
    - Un array JSON de objetos billing.
    - Un objeto JSON único (se envuelve en lista automáticamente).

    Args:
        input_file: Ruta al archivo JSON con los mensajes.

    Returns:
        Lista de diccionarios con los datos de cada mensaje.

    Raises:
        FileNotFoundError: Si el archivo no existe.
        ValueError: Si el contenido no es un array ni un objeto JSON válido.
    """
    path = Path(input_file)
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo de entidades: {path}")

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        messages = data
    elif isinstance(data, dict):
        messages = [data]
    else:
        raise ValueError(f"El archivo {input_file} debe contener un objeto o array JSON válido.")

    if not messages:
        raise ValueError(f"El archivo {input_file} no contiene mensajes.")

    return messages

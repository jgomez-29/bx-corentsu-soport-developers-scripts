"""
Estructura del documento para la colección "uf-values".

Colección: uf-values

Documento:
    {
        "date": ISODate("2025-01-01T00:00:00.000Z"),
        "value": 38419.17
    }

Campos:
    - date   (datetime)  → Fecha del valor UF, con hora en 00:00:00 UTC
    - value  (float)     → Valor de la UF para esa fecha (con decimales, tal cual)

Ejemplo real:
    CSV dice: Día=1, Ene, valor="38.419,17", archivo="UF 2025.csv"
    → { "date": ISODate("2025-01-01T00:00:00.000Z"), "value": 38419.17 }
"""

from datetime import datetime, timezone
from typing import Dict, Any


def build_uf_document(year: int, month: int, day: int, value: float) -> Dict[str, Any]:
    """
    Construye un documento para insertar en la colección uf-value.

    Args:
        year: Año (ej: 2025)
        month: Mes (1-12)
        day: Día (1-31)
        value: Valor UF (float con decimales)

    Returns:
        Diccionario con { date: datetime, value: float }
    """
    return {
        "date": datetime(year, month, day, 0, 0, 0, tzinfo=timezone.utc),
        "value": value,
    }

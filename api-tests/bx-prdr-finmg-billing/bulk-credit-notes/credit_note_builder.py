"""
Builder del body para el endpoint bulk-credit-notes.

El array de elementos se carga desde archivos JSON pre-construidos en payloads/
para evitar generar listas grandes en memoria en cada ejecución.

Archivos disponibles en payloads/:
    elements_10.json   →  10 elementos
    elements_20.json   →  20 elementos
    elements_500.json  →  500 elementos
"""

import json
from pathlib import Path
from typing import Any, Dict, List

# Directorio donde están los payloads pre-construidos
_PAYLOADS_DIR = Path(__file__).parent / "payloads"


def load_elements(elements_count: int) -> List[Dict[str, Any]]:
    """
    Carga el array de elementos desde el JSON correspondiente.

    Args:
        elements_count: Cantidad de elementos (10, 20 o 500)

    Returns:
        Lista de elementos cargada desde payloads/elements_<N>.json

    Raises:
        FileNotFoundError: Si no existe el archivo para ese count
    """
    payload_file = _PAYLOADS_DIR / f"elements_{elements_count}.json"
    if not payload_file.exists():
        available = sorted(p.stem for p in _PAYLOADS_DIR.glob("elements_*.json"))
        raise FileNotFoundError(
            f"No existe payload para {elements_count} elementos.\n"
            f"Archivo esperado: {payload_file}\n"
            f"Disponibles: {', '.join(available)}"
        )
    with open(payload_file, encoding="utf-8-sig") as f:
        return json.load(f)


def build_body(bulk_id: str, elements_count: int = 500) -> Dict[str, Any]:
    """
    Construye el body del request para bulk-credit-notes.

    Args:
        bulk_id:        ID único del bulk (ej: "268d0a1d-8b96-4667-8e2f-d7e42cbbb9c3")
        elements_count: Cantidad de elementos a incluir (debe existir JSON en payloads/)

    Returns:
        Dict con "bulkId" y "elements" cargados desde archivo JSON
    """
    return {
        "bulkId": bulk_id,
        "elements": load_elements(elements_count),
    }

"""
Cliente HTTP para consultar la API de generación de boletas.

API Endpoint:
    GET {base_url}/finmg/payment-process-massive/payment-documents/requests/{requestId}

Response (paginada por cursor):
    {
        "data": [ ... documentos ... ],
        "pagination": { "limit": 100, "hasMore": true, "nextCursor": "..." }
    }
    Se realizan solicitudes sucesivas con el cursor hasta que hasMore sea false.
"""

import requests
from urllib.parse import urlencode, urlparse, parse_qs, urlunparse
from typing import Any, Dict, List, Optional, Tuple


def _url_with_cursor(url: str, cursor: Optional[str]) -> str:
    """Añade el parámetro nextCursor a la URL si se proporciona (según contrato de la API)."""
    if not cursor:
        return url
    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    query["nextCursor"] = [cursor]
    new_query = urlencode(query, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def _parse_page_body(body: Any) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Parsea el cuerpo de una respuesta (paginada o lista directa).
    Returns:
        (lista de documentos de esta página, next_cursor o None si no hay más)
    """
    if isinstance(body, dict) and "data" in body:
        page_data = body.get("data")
        items = list(page_data) if isinstance(page_data, list) else []
        pagination = body.get("pagination") or {}
        next_cursor = pagination.get("nextCursor") if pagination.get("hasMore") else None
        return (items, next_cursor)
    if isinstance(body, list):
        return (body, None)
    raise ValueError(
        f"Formato de respuesta no reconocido: se esperaba un objeto con 'data' o una lista, "
        f"se obtuvo {type(body)}"
    )


def fetch_boletas_data(base_url: str, request_id: str, endpoint: str, timeout: int = 30) -> List[Dict[str, Any]]:
    """
    Consulta la API para obtener la lista de boletas, recorriendo todas las páginas
    cuando la API usa paginación por cursor.

    Args:
        base_url: URL base de la API
        request_id: ID del request a consultar
        endpoint: Endpoint de la API (sin base URL ni request ID)
        timeout: Timeout en segundos por petición

    Returns:
        Lista de todos los documentos JSON (todas las páginas concatenadas)

    Raises:
        requests.RequestException: Si falla la petición HTTP
        ValueError: Si la respuesta no tiene el formato esperado
    """
    base_request_url = f"{base_url.rstrip('/')}{endpoint}{request_id}"
    headers = {"accept": "application/json"}
    all_data: List[Dict[str, Any]] = []
    cursor: Optional[str] = None

    try:
        while True:
            url = _url_with_cursor(base_request_url, cursor)
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            body = response.json()
            items, next_cursor = _parse_page_body(body)
            all_data.extend(items)
            if next_cursor is None:
                break
            cursor = next_cursor
        return all_data

    except requests.exceptions.Timeout:
        raise requests.RequestException(f"Timeout al consultar la API: {base_request_url}")
    except requests.exceptions.ConnectionError as e:
        raise requests.RequestException(
            f"Error de conexión al consultar la API: {base_request_url}\nDetalle: {e}"
        )
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else "?"
        raise requests.RequestException(
            f"Error HTTP {status} al consultar la API: {base_request_url}\nDetalle: {e}"
        )
    except requests.exceptions.RequestException as e:
        raise requests.RequestException(f"Error inesperado al consultar la API: {base_request_url}\nDetalle: {e}")

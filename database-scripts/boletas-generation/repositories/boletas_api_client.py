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
    """Añade el parámetro cursor a la URL si se proporciona."""
    if not cursor:
        return url
    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    # Algunas implementaciones devuelven `nextCursor` en la respuesta,
    # pero esperan `cursor` en la siguiente petición.
    query["cursor"] = [cursor]
    query.pop("nextCursor", None)
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
        next_cursor = (
            pagination.get("nextCursor") if pagination.get("hasMore") else None
        )
        return (items, next_cursor)
    if isinstance(body, list):
        return (body, None)
    raise ValueError(
        f"Formato de respuesta no reconocido: se esperaba un objeto con 'data' o una lista, "
        f"se obtuvo {type(body)}"
    )


def _validate_pagination_state(
    page_number: int,
    max_pages: int,
    items: List[Dict[str, Any]],
    cursor: Optional[str],
    next_cursor: Optional[str],
    seen_cursors: set,
) -> None:
    """Valida condiciones de seguridad de la paginación."""
    if page_number > max_pages:
        raise ValueError(
            f"Paginación excedió el máximo de páginas permitido ({max_pages}). "
            "Posible loop de cursor en la API."
        )

    if next_cursor is None:
        return

    if next_cursor == cursor or next_cursor in seen_cursors:
        raise ValueError(
            "Se detectó paginación cíclica (cursor repetido). "
            "La API no está avanzando de página."
        )

    if len(items) == 0:
        raise ValueError(
            "La API indicó más páginas, pero devolvió una página vacía. "
            "Se detiene para evitar loop infinito."
        )


def _format_cursor_display(cursor: Optional[str]) -> str:
    """Devuelve una versión corta del cursor para logging."""
    if not cursor:
        return "<sin-cursor>"
    if len(cursor) <= 24:
        return cursor
    return cursor[:24] + "..."


def _log_page_progress(
    page_number: int,
    cursor_display: str,
    page_items: int,
    total_items: int,
    has_more: bool,
    verbose_page_log: bool,
) -> None:
    """Imprime progreso de paginación en modo compacto o detallado."""
    if verbose_page_log:
        print(f"  [API] Página {page_number}: solicitando (cursor={cursor_display})")
        print(
            f"  [API] Página {page_number}: recibidos={page_items} "
            f"| acumulado={total_items} | has_more={has_more}"
        )
        return

    print(
        f"  [API] Página {page_number} (cursor={cursor_display}): "
        f"recibidos={page_items} | acumulado={total_items} | has_more={has_more}"
    )


def _fetch_page(
    base_request_url: str,
    headers: Dict[str, str],
    timeout: int,
    cursor: Optional[str],
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Solicita y parsea una página de la API."""
    url = _url_with_cursor(base_request_url, cursor)
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    body = response.json()
    return _parse_page_body(body)


def fetch_boletas_data(
    base_url: str,
    request_id: str,
    endpoint: str,
    timeout: int = 30,
    max_pages: int = 1000,
    verbose_page_log: bool = False,
) -> List[Dict[str, Any]]:
    """
    Consulta la API para obtener la lista de boletas, recorriendo todas las páginas
    cuando la API usa paginación por cursor.

    Args:
        base_url: URL base de la API
        request_id: ID del request a consultar
        endpoint: Endpoint de la API (sin base URL ni request ID)
        timeout: Timeout en segundos por petición
        max_pages: Máximo de páginas permitidas para evitar loops infinitos
        verbose_page_log: Si es True, imprime dos líneas por página (solicitud + respuesta)

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
    seen_cursors = set()

    try:
        page_number = 0
        while True:
            page_number += 1
            cursor_display = _format_cursor_display(cursor)
            items, next_cursor = _fetch_page(
                base_request_url=base_request_url,
                headers=headers,
                timeout=timeout,
                cursor=cursor,
            )
            all_data.extend(items)
            has_more = next_cursor is not None
            _log_page_progress(
                page_number=page_number,
                cursor_display=cursor_display,
                page_items=len(items),
                total_items=len(all_data),
                has_more=has_more,
                verbose_page_log=verbose_page_log,
            )

            _validate_pagination_state(
                page_number=page_number,
                max_pages=max_pages,
                items=items,
                cursor=cursor,
                next_cursor=next_cursor,
                seen_cursors=seen_cursors,
            )

            if next_cursor is None:
                break

            seen_cursors.add(next_cursor)
            cursor = next_cursor
        return all_data

    except requests.exceptions.Timeout:
        raise requests.RequestException(
            f"Timeout al consultar la API (>{timeout}s): {base_request_url}"
        )
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
        raise requests.RequestException(
            f"Error inesperado al consultar la API: {base_request_url}\nDetalle: {e}"
        )

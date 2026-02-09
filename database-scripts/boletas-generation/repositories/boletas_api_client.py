"""
Cliente HTTP para consultar la API de generación de boletas.

API Endpoint:
    GET {base_url}/finmg/payment-process-massive/payment-documents/requests/{requestId}

Response:
    Lista de documentos JSON con información de boletas (éxitos y errores)
"""

import requests
from typing import List, Dict, Any


def fetch_boletas_data(base_url: str, request_id: str, endpoint: str, timeout: int = 30) -> List[Dict[str, Any]]:
    """
    Consulta la API para obtener la lista de boletas.

    Args:
        base_url: URL base de la API
        request_id: ID del request a consultar
        endpoint: Endpoint de la API (sin base URL ni request ID)
        timeout: Timeout en segundos

    Returns:
        Lista de documentos JSON

    Raises:
        requests.RequestException: Si falla la petición HTTP
        ValueError: Si la respuesta no es una lista
    """
    url = f"{base_url.rstrip('/')}{endpoint}{request_id}"

    headers = {
        "accept": "application/json",
    }

    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()

        data = response.json()

        if not isinstance(data, list):
            raise ValueError(f"Se esperaba una lista en la respuesta, pero se obtuvo: {type(data)}")

        return data

    except requests.exceptions.Timeout:
        raise requests.RequestException(f"Timeout al consultar la API: {url}")
    except requests.exceptions.ConnectionError as e:
        raise requests.RequestException(f"Error de conexión al consultar la API: {url}\nDetalle: {e}")
    except requests.exceptions.HTTPError as e:
        raise requests.RequestException(f"Error HTTP {response.status_code} al consultar la API: {url}\nDetalle: {e}")
    except requests.exceptions.RequestException as e:
        raise requests.RequestException(f"Error inesperado al consultar la API: {url}\nDetalle: {e}")
    except ValueError as e:
        raise

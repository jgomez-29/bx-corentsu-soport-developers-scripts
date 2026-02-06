"""
Cliente HTTP para consumir la API de envío de notificaciones.

API:
    POST {BASE_URL}/notif/on-demand/v1/ses

Referencia del curl original:
    curl --location '{BASE_URL}/notif/on-demand/v1/ses'
         --header 'X-Team-Domain: Domain'
         --header 'X-Team-Subdomain: Subdomain'
         --header 'X-Team-Capability: Capability'
         --header 'Content-Type: application/json'
         --data-raw '{ ... }'
"""

import requests
import json
import urllib3
from typing import Dict, Any

# Desactivar warnings de SSL para certificados internos/privados
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# Endpoint relativo (se concatena con BASE_URL de config)
NOTIFICATION_ENDPOINT = "/notif/on-demand/v1/ses"


def send_notification(
    base_url: str,
    payload: Dict[str, Any],
    headers: Dict[str, str],
    timeout: int = 30,
) -> Dict[str, Any]:
    """
    Envía una notificación a la API.

    Args:
        base_url: URL base del servicio (ej: "http://bx-app-prdr-notif-dispatch-gateway.qa-ns-clientes-posaut")
        payload: Diccionario con el body del request (ver entities/notification_request.py)
        headers: Headers del request (ver entities/notification_request.py → NOTIFICATION_HEADERS)
        timeout: Timeout en segundos para la petición

    Returns:
        Diccionario con:
            - status: "OK" o "ERROR"
            - status_code: Código HTTP de respuesta
            - response: Body de la respuesta (si aplica)
            - error: Mensaje de error (si aplica)
    """
    url = f"{base_url.rstrip('/')}{NOTIFICATION_ENDPOINT}"

    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=timeout,
            verify=False,  # Certificado interno/privado (qa.blue.private)
        )

        if response.ok:
            return {
                "status": "OK",
                "status_code": response.status_code,
                "response": _safe_json(response),
            }
        else:
            return {
                "status": "ERROR",
                "status_code": response.status_code,
                "response": _safe_json(response),
                "error": f"HTTP {response.status_code}: {response.text[:200]}",
            }

    except requests.exceptions.Timeout:
        return {
            "status": "ERROR",
            "status_code": None,
            "error": f"Timeout después de {timeout}s al llamar a {url}",
        }
    except requests.exceptions.ConnectionError as e:
        return {
            "status": "ERROR",
            "status_code": None,
            "error": f"Error de conexión a {url}: {str(e)[:200]}",
        }
    except Exception as e:
        return {
            "status": "ERROR",
            "status_code": None,
            "error": f"Error inesperado: {str(e)[:200]}",
        }


def _safe_json(response: requests.Response) -> Any:
    """Intenta parsear la respuesta como JSON; si falla, retorna el texto."""
    try:
        return response.json()
    except (json.JSONDecodeError, ValueError):
        return response.text[:500]

"""
Cliente HTTP para el endpoint credit-note-statistics.

Realiza un GET con verify=False para soportar certificados SSL internos
(*.dev.blueexpress.tech, *.stg.blueexpress.tech).
"""

import time
import urllib3
from typing import Any, Dict

import requests

# Desactivar warnings de SSL para certificados internos/privados
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def get_request(url: str, timeout: int = 30) -> Dict[str, Any]:
    """
    Realiza un GET HTTP y mide el tiempo de respuesta.

    Args:
        url:     URL completa del endpoint (con request_id incluido)
        timeout: Timeout en segundos (default: 30)

    Returns:
        Dict con:
            - status:      "OK" o "ERROR"
            - status_code: Código HTTP (int) o None si no hubo respuesta
            - elapsed_ms:  Tiempo de respuesta en milisegundos (int)
            - response:    Body de la respuesta (dict o str, si aplica)
            - error:       Mensaje de error (str o None)
    """
    start = time.time()
    try:
        response = requests.get(
            url,
            timeout=timeout,
            verify=False,  # Certificado interno/privado
        )
        elapsed_ms = int((time.time() - start) * 1000)

        try:
            response_body = response.json()
        except Exception:
            response_body = response.text

        if response.ok:
            return {
                "status": "OK",
                "status_code": response.status_code,
                "elapsed_ms": elapsed_ms,
                "response": response_body,
                "error": None,
            }
        return {
            "status": "ERROR",
            "status_code": response.status_code,
            "elapsed_ms": elapsed_ms,
            "response": response_body,
            "error": f"HTTP {response.status_code}",
        }

    except requests.exceptions.Timeout:
        elapsed_ms = int((time.time() - start) * 1000)
        return {
            "status": "ERROR",
            "status_code": None,
            "elapsed_ms": elapsed_ms,
            "response": None,
            "error": "Timeout",
        }
    except requests.exceptions.ConnectionError as exc:
        elapsed_ms = int((time.time() - start) * 1000)
        return {
            "status": "ERROR",
            "status_code": None,
            "elapsed_ms": elapsed_ms,
            "response": None,
            "error": f"ConnectionError: {exc}",
        }
    except Exception as exc:
        elapsed_ms = int((time.time() - start) * 1000)
        return {
            "status": "ERROR",
            "status_code": None,
            "elapsed_ms": elapsed_ms,
            "response": None,
            "error": str(exc),
        }

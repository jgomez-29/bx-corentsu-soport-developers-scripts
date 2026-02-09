"""
Estructura de la respuesta de la API de generación de boletas.

Respuesta de la API: lista de documentos con información de boletas.

Documento exitoso:
    {
        "_id": "6983476467f256303ea6755b",
        "requestId": "...",
        "documentToCreate": {
            "HESCode": 176099,
            "BTECode": 59942,
            ...
        },
        "status": "BTE_CREATED",
        ...
    }

Documento con error:
    {
        "_id": "6983476e67f256303ea6759d",
        "requestId": "...",
        "documentToCreate": {
            "HESCode": 176430,
            "BTECode": null,
            ...
        },
        "status": "BTE_CREATE_ERROR",
        "errorDetails": {
            "message": "communeName: Commune 'ANCUD' does not exist in region 'REGION DE LOS RIOS'",
            "timestamp": "2026-02-04T14:16:45.273Z"
        },
        ...
    }

Campos clave:
    - documentToCreate.HESCode: Código que matchea con el Excel
    - documentToCreate.BTECode: Código de boleta (si exitoso)
    - status: Estado del documento
    - errorDetails.message: Mensaje de error detallado (si existe)
"""

from typing import Optional, Dict, Any


def extract_hes_code(document: Dict[str, Any]) -> Optional[int]:
    """
    Extrae el HESCode del documento.

    Args:
        document: Documento de la API

    Returns:
        HESCode como entero o None si no existe
    """
    try:
        return document.get("documentToCreate", {}).get("HESCode")
    except (AttributeError, TypeError):
        return None


def extract_bte_code(document: Dict[str, Any]) -> Optional[int]:
    """
    Extrae el BTECode del documento.

    Args:
        document: Documento de la API

    Returns:
        BTECode como entero o None si no existe
    """
    try:
        return document.get("documentToCreate", {}).get("BTECode")
    except (AttributeError, TypeError):
        return None


def extract_status(document: Dict[str, Any]) -> str:
    """
    Extrae el status del documento.

    Args:
        document: Documento de la API

    Returns:
        Status como string, "UNKNOWN" si no existe
    """
    return document.get("status", "UNKNOWN")


def extract_error_message(document: Dict[str, Any]) -> Optional[str]:
    """
    Extrae el mensaje de error del documento.
    Prioriza errorDetails.message, si no existe usa status.

    Args:
        document: Documento de la API

    Returns:
        Mensaje de error o None si es exitoso
    """
    error_details = document.get("errorDetails", {})
    if error_details and "message" in error_details:
        return error_details.get("message")

    status = extract_status(document)
    if status != "BTE_CREATED":
        return status

    return None


def is_success(document: Dict[str, Any]) -> bool:
    """
    Determina si el documento fue exitoso.

    Args:
        document: Documento de la API

    Returns:
        True si status == "BTE_CREATED", False en caso contrario
    """
    return extract_status(document) == "BTE_CREATED"

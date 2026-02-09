"""
Configuración general para el script de generación de boletas.

Flujo:
    1. Lee Excel de entrada → extrae HESCode
    2. Llama API con requestId → obtiene respuestas (éxitos y errores)
    3. Hace match por HESCode
    4. Genera nuevo Excel con columnas: BOLETA y DETALLE_ERRORES

Variables de entorno requeridas (en .env de la raíz del repo):
    BOLETAS_API_URL      → URL base de la API
                           Ejemplo: http://localhost:3000
    BOLETAS_REQUEST_ID   → ID del request a consultar
                           Ejemplo: YmF0Y2hfMTc3MDIxMTE2MTQzMl8yODZlODlkMC1mYTU3LTQ1ODctOGY5MS0zOTc5YzAyNGM0MWQ=
"""

import os

# ============================================================================
# CONFIGURACIÓN: API
# ============================================================================

# URL base de la API (leída de variable de entorno)
BOLETAS_API_URL = os.getenv("BOLETAS_API_URL", "")

# Request ID a consultar (leído de variable de entorno)
BOLETAS_REQUEST_ID = os.getenv("BOLETAS_REQUEST_ID", "")

# Endpoint de la API (se construye con URL base + request ID)
API_ENDPOINT = "/finmg/payment-process-massive/payment-documents/requests/"

# ============================================================================
# CONFIGURACIÓN: ARCHIVOS
# ============================================================================

# Archivo Excel de entrada (en reports/)
INPUT_FILE = "SOPORT BTE - MIRO Flex Laboral Scl Ene26.xlsx"

# Directorio donde se guardará el Excel de salida
OUTPUT_DIR = "./output"

# ============================================================================
# CONFIGURACIÓN: LOGS
# ============================================================================

LOGS_DIR = "./logs"

# ============================================================================
# CONFIGURACIÓN: EJECUCIÓN
# ============================================================================

# Si es True, solo muestra lo que haría sin generar el Excel de salida
DRY_RUN = True

# Cantidad máxima de registros a procesar en modo DRY_RUN (0 = todos)
DRY_RUN_LIMIT = 10

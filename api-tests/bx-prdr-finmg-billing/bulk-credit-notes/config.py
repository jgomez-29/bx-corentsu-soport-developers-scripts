"""
Configuración general para la prueba de carga de bulk-credit-notes.

No requiere variables de entorno sensibles.
Las URLs de cada ambiente están en dev/config.py y qa/config.py.
"""

# ============================================================================
# CONFIGURACIÓN: AMBIENTE
# ============================================================================

# Ambiente a usar si no se elige en el prompt interactivo (dev | qa)
ENVIRONMENT = "qa"

# ============================================================================
# CONFIGURACIÓN: REQUEST BODY
# ============================================================================

# bulkId enviado en todos los requests (estático para pruebas de carga)
BULK_ID = "268d0a1d-8b96-4667-8e2f-d7e42cbbb9c3"

# Cantidad de elementos en el array "elements" de cada request
ELEMENTS_COUNT = 500

# ============================================================================
# CONFIGURACIÓN: EJECUCIÓN
# ============================================================================

# Cantidad de requests a enviar (default si no se ingresa por terminal)
TOTAL_REQUESTS = 10

# Duración total de la prueba en segundos.
# El delay entre requests se calcula automáticamente: DURATION_SECONDS / TOTAL_REQUESTS
# 0 = sin límite de tiempo (requests consecutivos, sin delay entre ellos)
DURATION_SECONDS = 0

# ============================================================================
# CONFIGURACIÓN: LOGS
# ============================================================================

LOGS_DIR = "./logs"

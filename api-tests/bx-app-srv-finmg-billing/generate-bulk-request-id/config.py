"""
Configuración general para la prueba de carga de generate-bulk-request-id.

El fileName en el body es dinámico: cada request genera un nombre único
basado en timestamp, número de request y un número aleatorio.

No requiere variables de entorno sensibles.
Las URLs de cada ambiente están en dev/config.py y qa/config.py.
"""

# ============================================================================
# CONFIGURACIÓN: AMBIENTE
# ============================================================================

# Ambiente a usar si no se elige en el prompt interactivo (dev | qa)
ENVIRONMENT = "qa"

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

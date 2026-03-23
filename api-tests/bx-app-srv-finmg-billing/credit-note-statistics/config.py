"""
Configuración general para la prueba de carga de credit-note-statistics.

No requiere variables de entorno sensibles.
Las URLs de cada ambiente están en dev/config.py y qa/config.py.
"""

# ============================================================================
# CONFIGURACIÓN: AMBIENTE
# ============================================================================

# Ambiente a usar si no se elige en el prompt interactivo (dev | qa)
ENVIRONMENT = "qa"

# ============================================================================
# CONFIGURACIÓN: REQUEST
# ============================================================================

# ID del bulk request a consultar (UUID)
# Se puede sobreescribir en el prompt interactivo al ejecutar
REQUEST_ID = "b1b42bfa-ecac-4162-8eb5-10aeefa6b4ba"

# ============================================================================
# CONFIGURACIÓN: EJECUCIÓN
# ============================================================================

# Cantidad de requests a enviar (default si no se ingresa por terminal)
TOTAL_REQUESTS = 10

# Duración total de la prueba en segundos.
# 0 = sin límite de tiempo (requests consecutivos, sin delay entre ellos)
DURATION_SECONDS = 0

# ============================================================================
# CONFIGURACIÓN: LOGS
# ============================================================================

LOGS_DIR = "./logs"

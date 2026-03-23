"""
Configuración del ambiente DEV para bulk-credit-notes.

No requiere variables de entorno.
"""

# URL base del servicio en DEV
BASE_URL = "http://soport.dev.blue.private"

# Endpoint del recurso
ENDPOINT = "/finmg/prdr/billing/v1/bulk-credit-notes"

# URL completa construida a partir de las anteriores
FULL_URL = f"{BASE_URL}{ENDPOINT}"

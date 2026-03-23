"""
Configuración del ambiente DEV para generate-bulk-request-id.

No requiere variables de entorno.
"""

# URL base del servicio en DEV
BASE_URL = "https://bx-app-srv-finmg-billings.dev.blueexpress.tech"

# Endpoint del recurso
ENDPOINT = "/finmg/billing/bff/v1/generate-bulk-request-id"

# URL completa construida a partir de las anteriores
FULL_URL = f"{BASE_URL}{ENDPOINT}"

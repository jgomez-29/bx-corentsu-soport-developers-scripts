"""
Configuración del ambiente QA (stage) para generate-bulk-request-id.

No requiere variables de entorno.
"""

# URL base del servicio en QA/Stage
BASE_URL = "https://bx-app-srv-finmg-billings.stg.blueexpress.tech"

# Endpoint del recurso
ENDPOINT = "/finmg/billing/bff/v1/generate-bulk-request-id"

# URL completa construida a partir de las anteriores
FULL_URL = f"{BASE_URL}{ENDPOINT}"

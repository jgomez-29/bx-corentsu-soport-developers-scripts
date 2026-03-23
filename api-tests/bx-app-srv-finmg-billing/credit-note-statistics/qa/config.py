"""
Configuración del ambiente QA (stage) para credit-note-statistics.

No requiere variables de entorno.
"""

# URL base del servicio en QA/Stage
BASE_URL = "https://bx-app-srv-finmg-billings.stg.blueexpress.tech"

# Plantilla del endpoint (el {request_id} se reemplaza en run.py)
ENDPOINT_TEMPLATE = (
    "/finmg/app-srv/billing/v1/credit-note-requests/{request_id}/statistics"
)

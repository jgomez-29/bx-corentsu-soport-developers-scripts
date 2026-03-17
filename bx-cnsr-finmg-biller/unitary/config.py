"""
Configuración GENERAL para biller-unitary (envío directo a SQS para pruebas de estrés).

Destino: solo SQS (queue-finmg-billing-document-request).
La configuración específica del ambiente está en dev/config.py y qa/config.py.

Entidad por ambiente:
  - Si INPUT_FILE está definido y existe dev/entities/dte-information.json o
    qa/entities/dte-information.json, se usa como plantilla (se replican N mensajes
    con identificadores únicos).
  - Si no hay archivo, se generan payloads sintéticos con la misma estructura.
"""

ENVIRONMENT = "dev"
TARGET = "sqs"

ENTITY_TYPE = "billingDocumentRequest"
EVENT_TYPE = "billingOrchestrated"

# Plantilla DteInformation por ambiente (ruta relativa a dev/ o qa/).
# Ejemplo: "entities/dte-information.json" → dev/entities/dte-information.json o qa/...
# Si no existe el archivo, el script genera mensajes sintéticos.
INPUT_FILE = "entities/dte-information.json"

DELAY_MS = 0
BATCH_SIZE = 100
MAX_CONCURRENT = 10
MAX_MESSAGES = 10
LOGS_DIR = "./logs"

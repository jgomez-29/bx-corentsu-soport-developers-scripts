"""
Configuración GENERAL para proforma-checkpoints (envío directo a SQS para pruebas de carga).

Destino: solo SQS (queue-finmg-proforma-checkpoints).
La configuración específica del ambiente está en dev/config.py y qa/config.py.

Estrategia de generación:
  - Si existe dev/entities/checkpoint-event.json o qa/entities/checkpoint-event.json,
    se usan todos los mensajes con el mismo orderId que la plantilla (permite probar
    el consumer golpeando siempre el mismo documento en Mongo; fácil de limpiar).
  - Si no hay archivo, se generan payloads sintéticos con ORDER_ID como orderId fijo.
"""

ENVIRONMENT = "dev"
TARGET = "sqs"

ENTITY_TYPE = "Orders"
EVENT_TYPE = "created or modified"

# Plantilla CheckpointEvent por ambiente (ruta relativa a dev/ o qa/).
# Ejemplo: "entities/checkpoint-event.json" → dev/entities/checkpoint-event.json
# Si no existe el archivo, el script genera mensajes sintéticos con ORDER_ID.
INPUT_FILE = "entities/checkpoint-event.json"

# orderId fijo para mensajes sintéticos (pruebas de carga sin plantilla).
# Todos los mensajes generados comparten este orderId; al terminar solo hay
# un documento de prueba en Mongo que limpiar.
ORDER_ID = "stress-load-test"

# Modo de envío: "parallel" (lotes con concurrencia) o "sequential" (uno por uno con delay)
SEND_MODE = "parallel"

DELAY_MS = 0
BATCH_SIZE = 100
MAX_CONCURRENT = 10
MAX_MESSAGES = 10
LOGS_DIR = "./logs"

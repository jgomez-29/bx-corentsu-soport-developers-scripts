"""
Configuración GENERAL para el script de envío de mensajes a SQS (órdenes consolidación).

La configuración específica de cada ambiente (queue URL, región) está en:
- dev/config.py
- qa/config.py
"""

# ============================================================================
# CONFIGURACIÓN: AMBIENTE
# ============================================================================

ENVIRONMENT = "qa"  # "dev" o "qa"

# Destino del mensaje: "sqs" = solo cola, "sns" = solo topic, "both" = cola y topic (poco común)
TARGET = "sqs"

# ============================================================================
# CONFIGURACIÓN COMÚN
# ============================================================================

MODE = "create"  # "create" o "modify"
ENTITY_TYPE = "order"
EVENT_TYPE = "orderCreated"
DELAY_MS = 0
SUBDOMAIN = "soport"
BUSINESS_CAPACITY = "ciclos"
LOGS_DIR = "./logs"

# ============================================================================
# CONFIGURACIÓN MODO CREATE
# ============================================================================

ORDER_ID_BASE = "TEST-ORDER-CONTAINER"
ORDER_ID_START = 1
TOTAL_MESSAGES = 3000
ORDER_TYPE = 3

# ============================================================================
# CONFIGURACIÓN MODO MODIFY
# ============================================================================

# Ruta relativa al folder del ambiente: dev/entities/ o qa/entities/
INPUT_FILE = "./entities/order-container.json"
ORDER_IDS_LIST = []
MODIFY_ORDER_TYPE = 3

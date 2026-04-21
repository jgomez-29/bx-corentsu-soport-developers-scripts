"""
Configuración GENERAL para el script de envío de mensajes a SQS para replicación de facturas.

Esta es la configuración general que aplica a todos los ambientes.
La configuración específica de cada ambiente (queue URL, región) está en:
- dev/config.py
- qa/config.py
"""

# ============================================================================
# CONFIGURACIÓN: AMBIENTE
# ============================================================================

# Ambiente de ejecución: "dev" o "qa"
ENVIRONMENT = "dev"  # Cambia aquí el ambiente: "dev" o "qa"

# Destino del mensaje: "sqs" = solo cola, "sns" = solo topic, "both" = cola y topic
TARGET = "sqs"

# ============================================================================
# CONFIGURACIÓN COMÚN
# ============================================================================

ENTITY_TYPE = "billedDocument"
EVENT_TYPE = "billingToBeReplicated"

DELAY_MS = 0
BATCH_SIZE = 10
MAX_CONCURRENT = 1
LOGS_DIR = "./logs"

# ============================================================================
# CONFIGURACIÓN: MENSAJES A ENVIAR
# ============================================================================

# Cantidad máxima de mensajes a enviar (0 = sin límite, usa la cantidad del archivo)
MAX_MESSAGES = 1

# Archivo JSON con los mensajes a enviar (ruta relativa al folder del ambiente)
INPUT_FILE = "./entities/billing.json"

"""
Configuración GENERAL para el script de envío de mensajes a SQS para proformas.

Esta es la configuración general que aplica a todos los ambientes.
La configuración específica de cada ambiente (queue URL, región) está en:
- dev/config.py
- qa/config.py
"""

# ============================================================================
# CONFIGURACIÓN: AMBIENTE
# ============================================================================

# Ambiente de ejecución: "dev" o "qa"
ENVIRONMENT = "qa"  # Cambia aquí el ambiente: "dev" o "qa"

# Destino del mensaje: "sqs" = solo cola, "sns" = solo topic, "both" = cola y topic (poco común)
TARGET = "sqs"

# ============================================================================
# CONFIGURACIÓN COMÚN
# ============================================================================

ENTITY_TYPE = "proforma"
EVENT_TYPE = "ProformaCreated"

DELAY_MS = 0
BATCH_SIZE = 100
MAX_CONCURRENT = 1
LOGS_DIR = "./logs"

# ============================================================================
# CONFIGURACIÓN: PROFORMAS A PROCESAR
# ============================================================================

# IMPORTANTE: Los proformaSeries deben existir en la base de datos.

# Opción 1: Archivo JSON (ruta relativa al folder del ambiente: dev/entities/ o qa/entities/)
INPUT_FILE = "./entities/proforma.json"

# Opción 2: Lista directa de proformaSeries
PROFORMA_SERIES_LIST = []

# Account opcional (None = se obtendrá de la BD)
ACCOUNT = None

MAX_MESSAGES = 1  # 0 = todos

"""
Configuración GENERAL para payment-process-unitary (SNS topic payment process, mensajes unitarios).

eventType: paymentProcessUnitary.
La configuración específica del ambiente está en dev/config.py y qa/config.py.
"""

ENVIRONMENT = "dev"
TARGET = "sns"

ENTITY_TYPE = "PaymentDocument"
EVENT_TYPE = "paymentProcessUnitary"

DELAY_MS = 0
BATCH_SIZE = 100
MAX_CONCURRENT = 3
MAX_MESSAGES = 10
LOGS_DIR = "./logs"

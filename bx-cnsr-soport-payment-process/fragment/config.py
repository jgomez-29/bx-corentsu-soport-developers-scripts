"""
Configuración GENERAL para payment-process-fragment (SNS topic payment process, mensajes fragment/masivo).

eventType: paymentProcessRequested.
La configuración específica del ambiente está en dev/config.py y qa/config.py.
"""

ENVIRONMENT = "dev"
TARGET = "sns"

ENTITY_TYPE = "PaymentProcess"
EVENT_TYPE = "paymentProcessRequested"

DELAY_MS = 0
BATCH_SIZE = 100
MAX_CONCURRENT = 3
MAX_MESSAGES = 10
LOGS_DIR = "./logs"

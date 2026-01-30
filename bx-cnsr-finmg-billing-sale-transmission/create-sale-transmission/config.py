"""
Configuración GENERAL para el script de envío de mensajes a SQS para SaleTransmission

Esta es la configuración general que aplica a todos los ambientes.
Define aquí: ambiente, cantidad de mensajes, modo de pruebas, etc.

La configuración específica de cada ambiente (queue URL, región AWS) está en:
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

# Tipo de entidad
ENTITY_TYPE = "saleTransmission"

# Tipo de evento (debe coincidir con el filtro de la subscription SNS)
# La queue escucha eventos con eventType: "SaleDispatched"
EVENT_TYPE = "SaleDispatched"

# Delay en milisegundos entre cada envío (0 = sin delay)
DELAY_MS = 0

# Configuración de envío en lotes (para optimizar cuando hay muchos mensajes)
# Tamaño del lote: cuántos mensajes enviar en paralelo por vez
BATCH_SIZE = 100  # Recomendado: 10-50 para balance entre velocidad y control
# Concurrencia máxima: cuántos lotes procesar simultáneamente
MAX_CONCURRENT = 1  # Recomendado: 5-20 según tu capacidad de red/AWS

# Carpeta donde se guardan los archivos de resultados/logs
# Los archivos se generan automáticamente con nombres descriptivos
LOGS_DIR = "./logs"


# ============================================================================
# CONFIGURACIÓN: SALE TRANSMISSION A PROCESAR
# ============================================================================

# Opción 1: Archivo JSON con lista de SaleTransmission
# Debe contener un array de objetos SaleTransmission con campos mínimos:
# - society, type, siiFolio, docType, account, costDetail
# - prepaidEmission (obligatorio si type="order")
INPUT_FILE = "./entities/sale-transmission.json"

# Opción 2: Lista directa de SaleTransmission
# Si usas esta opción, deja INPUT_FILE como None
SALE_TRANSMISSIONS_LIST = []

# Cantidad máxima de mensajes a enviar (0 = todos los que estén en el archivo/lista)
# Útil para limitar la cantidad durante pruebas
MAX_MESSAGES = 5000  # 0 = todos, o un número específico como 10, 100, etc.


# ============================================================================
# CONFIGURACIÓN: PRUEBAS DE ESTRÉS
# ============================================================================

# Habilitar modo de pruebas de estrés (genera mensajes automáticamente)
STRESS_TEST_ENABLED = False

# Base para generar siiFolio incrementales
# Ejemplo: "TEST-SII" generará: TEST-SII-000001, TEST-SII-000002, etc.
STRESS_TEST_BASE_SII_FOLIO = "TEST-SII"

# Número inicial del contador
STRESS_TEST_START = 1

# Archivo JSON con template de SaleTransmission para pruebas de estrés
# Este template se usará como base y solo se modificarán siiFolio y orderId
STRESS_TEST_TEMPLATE_FILE = "./entities/sale-transmission.json"

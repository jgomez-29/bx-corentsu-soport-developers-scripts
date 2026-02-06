"""
Configuración general para el script de reenvío de notificaciones.

Flujo:
    1. Lee CSV (reports/) → obtiene orderIds y emails (#recipient)
    2. Consulta MongoDB orders → obtiene siiFolio
    3. Consulta MongoDB invoices → obtiene siiDocumentPath y totalToPay
    4. Llama a la API de notificaciones con los datos recolectados (usando email del CSV)

Variables de entorno requeridas (en .env de la raíz del repo):
    MONGO_URI       → URI completa de conexión a MongoDB
                      Ejemplo: mongodb+srv://user:pass@cluster.mongodb.net/
    MONGO_DATABASE  → Nombre de la base de datos
                      Ejemplo: soport-orders
"""

import os

# ============================================================================
# CONFIGURACIÓN: MONGODB
# ============================================================================

# URI de conexión a MongoDB (leída de variable de entorno)
# Ejemplo: mongodb+srv://user:pass@corentsu-qas-pl-0.d1wdm.mongodb.net/
MONGO_URI = os.getenv("MONGO_URI", "")

# Base de datos donde están las colecciones orders e invoices
MONGO_DATABASE = os.getenv("MONGO_DATABASE", "")

# ============================================================================
# CONFIGURACIÓN: API DE NOTIFICACIONES
# ============================================================================

# URL base del servicio de notificaciones (ajustar según ambiente)
NOTIFICATION_API_BASE_URL = "https://bx-app-prdr-notif-dispatch-gateway.blue.private"

# Template de correo a utilizar
TEMPLATE_NAME = "billing-core-order-biling-mail"

# Dirección de envío
FROM_ADDRESS = "noreply@blue.cl"

# Email destino para modo DRY_RUN (pruebas). Se usa en lugar del email del CSV.
# En modo normal (DRY_RUN=False) se usa el email (#recipient) del CSV de errores.
DRY_RUN_EMAIL = "johann.gomez@blue.cl"

# ============================================================================
# CONFIGURACIÓN: CSV DE ENTRADA
# ============================================================================

# Ruta al archivo CSV con los errores de notificación (relativa a este script)
CSV_FILE = "./reports/notification-errors.csv"

# ============================================================================
# CONFIGURACIÓN: LOGS
# ============================================================================

LOGS_DIR = "./logs"

# ============================================================================
# CONFIGURACIÓN: EJECUCIÓN
# ============================================================================

# Delay entre envíos de notificación (ms) para no saturar la API
DELAY_MS = 500

# Si es True, envía las notificaciones al DRY_RUN_EMAIL en lugar de al buyer.email real.
# Si es False, envía al buyer.email real de cada orden.
DRY_RUN = True

# Cantidad máxima de registros a procesar en modo DRY_RUN.
# Solo aplica cuando DRY_RUN=True. Útil para probar con unos pocos antes de lanzar todo.
#   0 = procesar todos los registros del CSV (sin límite)
#   N = procesar solo los primeros N registros
# En modo real (DRY_RUN=False) se ignora y siempre se procesan todos.
DRY_RUN_LIMIT = 5

# ============================================================================
# CONFIGURACIÓN: REINTENTO DE FALLIDOS
# ============================================================================

# Si es True, ignora CSV_FILE y lee los orderIds fallidos del JSON indicado en RETRY_FILE.
# Si es False, usa CSV_FILE normalmente.
RETRY_FAILED = False

# Ruta al JSON de log de una ejecución anterior (relativa a este script).
# Solo se usa cuando RETRY_FAILED=True.
# Ejemplo: "./logs/resend_20260206_143000.json"
RETRY_FILE = ""

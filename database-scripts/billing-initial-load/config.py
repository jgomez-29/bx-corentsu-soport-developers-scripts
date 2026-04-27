"""
Configuración para el script billing-initial-load.

Variables de entorno requeridas (en .env de la raíz del repo):
    MONGO_URI         → URI de conexión a MongoDB
    MONGO_DATABASE    → Nombre de la base de datos
    ORACLE_DSN        → DSN de conexión Oracle (host:puerto/servicio)
    ORACLE_USER       → Usuario Oracle
    ORACLE_PASSWORD   → Contraseña Oracle
"""

import os

# ============================================================================
# CONFIGURACIÓN: MONGODB
# ============================================================================

MONGO_URI = os.getenv("MONGO_URI", "")
MONGO_DATABASE = os.getenv("MONGO_DATABASE", "")

# ============================================================================
# CONFIGURACIÓN: ORACLE (LEGADO)
# ============================================================================

ORACLE_DSN = os.getenv("ORACLE_DSN", "")
ORACLE_USER = os.getenv("ORACLE_USER", "")
ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD", "")

# ============================================================================
# CONFIGURACIÓN: EJECUCIÓN
# ============================================================================

# Fechas por defecto (solo usadas si stdin no es interactivo)
START_DATE = ""   # Formato: YYYY-MM-DD
END_DATE = ""     # Formato: YYYY-MM-DD

# Ruta al archivo de texto con las cuentas a procesar (una por línea).
# Ruta relativa a la carpeta del script o absoluta.
# Vacío = se solicita interactivamente.
ACCOUNTS_FILE = "accounts/cuentas.txt"  # Ejemplo: "accounts/cuentas.txt"

# Tamaño del lote de OS a procesar por iteración del cursor
BATCH_SIZE = 1000

# Cantidad de cuentas por lote en la query MongoDB.
# Con muchas cuentas en ACCOUNTS_FILTER, dividir en lotes reduce
# el tamaño de cada query y el uso de recursos en la base de datos.
ACCOUNT_BATCH_SIZE = 500

# ============================================================================
# CONFIGURACIÓN: DRY_RUN
# ============================================================================

# Si es True, simula el proceso sin escribir en MongoDB.
# Por seguridad, el valor por defecto es True.
DRY_RUN = True

# Cantidad máxima de registros a procesar por día en modo DRY_RUN.
# 0 = sin límite
DRY_RUN_LIMIT = 100

# ============================================================================
# CONFIGURACIÓN: LOGS
# ============================================================================

LOGS_DIR = "./logs"

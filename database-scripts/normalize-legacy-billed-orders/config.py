"""
Configuración para el script de normalización de OS facturadas en legado Oracle.

Flujo:
    1. Consulta MongoDB colección 'orders' buscando OS sin billing.status='BILLED'
       cuya emissionDate esté en el rango [DATE_FROM, DATE_TO).
    2. Pagina los resultados por _id (keyset pagination, lotes de BATCH_SIZE).
    3. Por cada lote, consulta Oracle tabla DCBT con EEVV_NMR_ID IN (...)
       para obtener DCBT_NMR_FAC_PF (número de proforma).
    4. Actualiza MongoDB en bulk: billing.proformaId y billing.status = 'BILLED'.
    5. Genera log JSON en logs/ con resultados por OS.

Variables de entorno requeridas (en .env de la raíz del repo):
    MONGO_URI       → URI de conexión a MongoDB
                      Ejemplo: mongodb+srv://user:pass@cluster.mongodb.net/
    MONGO_DATABASE  → Nombre de la base de datos
                      Ejemplo: soport-orders
    ORACLE_DSN      → DSN de conexión a Oracle
                      Ejemplo: host:1521/service_name
    ORACLE_USER     → Usuario Oracle
                      Ejemplo: soport_ro
    ORACLE_PASSWORD → Contraseña Oracle
"""

import os

# ============================================================================
# CONFIGURACIÓN: MONGODB
# ============================================================================

MONGO_URI = os.getenv("MONGO_URI", "")
MONGO_DATABASE = os.getenv("MONGO_DATABASE", "")

# ============================================================================
# CONFIGURACIÓN: ORACLE LEGADO
# ============================================================================

ORACLE_DSN = os.getenv("ORACLE_DSN", "")
ORACLE_USER = os.getenv("ORACLE_USER", "")
ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD", "")

# ============================================================================
# CONFIGURACIÓN: EJECUCIÓN
# ============================================================================

# Si es True, simula el proceso sin modificar MongoDB. Por defecto True (seguro).
DRY_RUN = True

# Tamaño de lote para paginación MongoDB y consultas Oracle (máximo 1000).
BATCH_SIZE = 1000

# Rango de fechas a procesar (formato YYYY-MM-DD).
# Se usa como fallback cuando el script no es interactivo (sys.stdin.isatty() == False).
DATE_FROM = ""
DATE_TO = ""

# ============================================================================
# CONFIGURACIÓN: LOGS
# ============================================================================

LOGS_DIR = "./logs"

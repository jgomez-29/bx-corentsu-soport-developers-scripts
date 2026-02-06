"""
Configuración general para el script de importación de valores UF.

Flujo:
    1. Lee CSVs de uf-reports/ → genera registros { date, value }
    2. Verifica cuáles ya existen en MongoDB
    3. Inserta solo los nuevos (bulk insert)

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
MONGO_URI = os.getenv("MONGO_URI", "")

# Base de datos
MONGO_DATABASE = os.getenv("MONGO_DATABASE", "")

# ============================================================================
# CONFIGURACIÓN: CSV DE ENTRADA
# ============================================================================

# Directorio con los archivos CSV de valores UF (relativa a este script)
UF_REPORTS_DIR = "./uf-reports"

# Patrón de nombre de archivo: "UF YYYY.csv"
# El año se extrae del nombre del archivo

# ============================================================================
# CONFIGURACIÓN: LOGS
# ============================================================================

LOGS_DIR = "./logs"

# ============================================================================
# CONFIGURACIÓN: EJECUCIÓN
# ============================================================================

# Si es True, solo muestra lo que haría sin insertar en la DB
DRY_RUN = True

# Cantidad máxima de registros a procesar en modo DRY_RUN (0 = todos)
DRY_RUN_LIMIT = 10

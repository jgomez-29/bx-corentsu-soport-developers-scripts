# Script de Envío de Mensajes a SQS - Proforma Detailed

Script para enviar mensajes a la queue `queue-finmg-proforma-detailed` para procesar proformas.

**⚠️ IMPORTANTE:** Los `proformaSeries` deben existir en la base de datos. Este script solo envía mensajes para proformas reales que ya están en la colección `proformas` de MongoDB.

## 📁 Archivo de Configuración

El script usa un archivo Python `config.py` que permite comentarios y es más flexible:

### Estructura de `config.py`

El archivo está organizado en secciones claras con comentarios explicativos:

```python
# ============================================================================
# CONFIGURACIÓN COMÚN
# ============================================================================

ENTITY_TYPE = "proforma"
EVENT_TYPE = "ProformaCreated"  # Siempre este evento
QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/..."
REGION = "us-east-1"
DELAY_MS = 0
LOGS_DIR = "./logs"

# ============================================================================
# CONFIGURACIÓN: PROFORMAS A PROCESAR
# ============================================================================

# IMPORTANTE: Los proformaSeries deben existir en la base de datos.

# Opción 1: Archivo JSON con lista de proformaSeries
INPUT_FILE = "./entities/proforma.json"

# Opción 2: Lista directa de proformaSeries
PROFORMA_SERIES_LIST = []  # Ejemplo: ["PROF-2024-001", "PROF-2024-002"]

# Account opcional (si no se especifica, se omite del mensaje)
ACCOUNT = None  # None para omitir, o un string como "ACC001"
```

**Ventajas de usar Python:**
- Puedes agregar comentarios explicativos
- Más flexible y fácil de editar
- Validación en tiempo de importación
- Puedes usar expresiones Python si es necesario

## Uso

### Opción 1: Cargar desde archivo JSON

1. Edita `config.py`:
   ```python
   INPUT_FILE = "./entities/proforma.json"
   PROFORMA_SERIES_LIST = []
   ACCOUNT = None  # Opcional
   ```
2. Crea o edita el archivo `./entities/proforma.json`:
   ```json
   [
     {"proformaSerie": "PROF-2024-001"},
     {"proformaSerie": "PROF-2024-002"}
   ]
   ```
   O simplemente:
   ```json
   ["PROF-2024-001", "PROF-2024-002"]
   ```
3. Ejecuta el script:
   ```bash
   python send_message.py
   ```

### Opción 2: Usar lista directa

1. Edita `config.py`:
   ```python
   INPUT_FILE = None
   PROFORMA_SERIES_LIST = ["PROF-2024-001", "PROF-2024-002", "PROF-2024-003"]
   ACCOUNT = None  # Opcional
   ```
2. Ejecuta el script:
   ```bash
   python send_message.py
   ```

**⚠️ IMPORTANTE:** 
- Los `proformaSeries` especificados **deben existir** en la base de datos en la colección `proformas`
- El servicio buscará cada proforma usando: `db.proformas.findOne({ "proformaSerie": "..." })`
- Si una proforma no existe, el servicio no procesará ese mensaje (solo registrará una advertencia)

## Estructura del Mensaje

El mensaje mínimo requerido es:

```json
{
  "proformaSerie": "PROF-2024-001"
}
```

El campo `account` es opcional. Si no se especifica, el servicio lo obtendrá de la proforma en la base de datos.

Ejemplo con account:
```json
{
  "proformaSerie": "PROF-2024-001",
  "account": "ACC001"
}
```

## Log de ProformaSeries

Todos los proformaSeries procesados se guardan automáticamente en archivos JSON dentro de la carpeta `./logs/`. Los archivos se generan con nombres descriptivos que incluyen la fecha/hora:

- `proforma_series_20260115_143022.json`

Cada archivo contiene:
- El total de proformaSeries procesadas
- La lista completa de proformaSeries
- Un timestamp de cuando se generó

Estos archivos te permiten:
- Identificar fácilmente los mensajes enviados
- Ver un resumen de lo que se procesó

## Variables de Entorno

En el archivo `.env` en la raíz del repo solo se usan datos sensibles:

- `AWS_REGION`: Región de AWS
- `AWS_ACCOUNT_ID`: ID de la cuenta AWS

Los nombres de la cola y del topic (no sensibles) están definidos en `dev/config.py` y `qa/config.py` (`QUEUE_NAME`, `TOPIC_NAME`).

## Ejemplo de Salida

```
============================================================
=== CONFIGURACIÓN ===
============================================================
🔧 Configuración de Proformas:
   • Archivo: ./entities/proforma.json
   • Account: No especificado (se obtendrá de la BD)

⚠️  IMPORTANTE: Los proformaSeries deben existir en la base de datos
   en la colección 'proformas'. El servicio buscará cada proforma por su proformaSerie.

🌐 Configuración de Queue:
   • Tipo entidad: proforma
   • Tipo evento: ProformaCreated
   • Cola SQS: https://sqs.us-east-1.amazonaws.com/...
   • Región: us-east-1
   • Delay entre mensajes: 0ms

📝 Logs se guardan en: ./logs/
============================================================
```

## Requisitos

- El `proformaSerie` debe existir en la colección `proformas` de MongoDB
- El servicio buscará la proforma usando: `db.proformas.findOne({ "proformaSerie": "..." })`
- Si la proforma no existe, el servicio no procesará el mensaje (solo registrará una advertencia)

## Verificación en MongoDB

Antes de enviar mensajes, puedes verificar que las proformas existen:

```javascript
// Verificar una proforma específica
db.proformas.findOne({ "proformaSerie": "TEST-PROFORMA-000001" })

// Verificar múltiples proformas
db.proformas.find({ 
  "proformaSerie": { 
    $in: ["TEST-PROFORMA-000001", "TEST-PROFORMA-000002"] 
  } 
})
```

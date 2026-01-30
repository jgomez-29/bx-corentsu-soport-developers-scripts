# Script de Envío de Mensajes a SQS

Script para enviar mensajes a la queue `queue-soport-erp-orders-consolidation-01` con soporte para crear o modificar órdenes.

## 📁 Archivo de Configuración

El script usa un archivo Python `config.py` que permite comentarios y es más flexible:

### Estructura de `config.py`

El archivo está organizado en secciones claras con comentarios explicativos:

```python
# ============================================================================
# CONFIGURACIÓN COMÚN
# ============================================================================

MODE = "create"  # "create" o "modify"
ENTITY_TYPE = "order"
EVENT_TYPE = "orderCreated"  # "orderCreated", "orderModified", "created", "modified"
QUEUE_URL = "https://sqs.us-west-2.amazonaws.com/..."
REGION = "us-west-2"
DELAY_MS = 0
SUBDOMAIN = "soport"
BUSINESS_CAPACITY = "ciclos"
ORDER_IDS_LOG_FILE = "./generated_order_ids.json"

# ============================================================================
# CONFIGURACIÓN PARA MODO CREATE
# ============================================================================

ORDER_ID_BASE = "TEST-ORDER-CONTAINER"
ORDER_ID_START = 1
TOTAL_MESSAGES = 100
ORDER_TYPE = 3

# ============================================================================
# CONFIGURACIÓN PARA MODO MODIFY
# ============================================================================

INPUT_FILE = "./entities/order-container.json"
ORDER_IDS_LIST = []  # O especifica directamente: ["123", "456", "789"]
MODIFY_ORDER_TYPE = 3
```

**Ventajas de usar Python:**
- Puedes agregar comentarios explicativos
- Más flexible y fácil de editar
- Validación en tiempo de importación
- Puedes usar expresiones Python si es necesario

## Uso

### Modo CREATE (Generar órdenes nuevas)

1. Edita `config.py` y asegúrate de que `MODE = "create"`
2. Edita la sección CREATE con tus parámetros:
   ```python
   ORDER_ID_BASE = "TEST-ORDER-CONTAINER"
   ORDER_ID_START = 1
   TOTAL_MESSAGES = 3000
   ORDER_TYPE = 3
   ```
3. Ejecuta el script:
   ```bash
   python send_to_sqs.py
   ```

El script generará orderIds como:
- `TEST-ORDER-CONTAINER-000001`
- `TEST-ORDER-CONTAINER-000002`
- ...
- `TEST-ORDER-CONTAINER-003000`

### Modo MODIFY (Modificar órdenes existentes)

1. Edita `config.py` y cambia `MODE = "modify"`
2. Edita la sección MODIFY:
   
   **Opción A**: Usar archivo JSON
   ```python
   INPUT_FILE = "./entities/order-container.json"
   ORDER_IDS_LIST = []
   MODIFY_ORDER_TYPE = 3
   ```
   
   **Opción B**: Usar lista directa
   ```python
   INPUT_FILE = None
   ORDER_IDS_LIST = ["123456", "789012", "345678"]
   MODIFY_ORDER_TYPE = 3
   ```
3. Ejecuta el script:
   ```bash
   python send_to_sqs.py
   ```

## Log de OrderIds

Todos los orderIds procesados (creados o modificados) se guardan automáticamente en `generated_order_ids.json`. Este archivo te permite:

- Identificar fácilmente los registros de prueba en la base de datos
- Eliminar los registros después de las pruebas
- Ver un resumen de lo que se procesó

## Variables de Entorno

En el archivo `.env` en la raíz del repo solo se usan datos sensibles:

- `AWS_REGION`: Región de AWS
- `AWS_ACCOUNT_ID`: ID de la cuenta AWS

Los nombres de la cola y del topic están en `dev/config.py` y `qa/config.py` (`QUEUE_NAME`, `TOPIC_NAME`). Opcional: `EVENT_BUSINESS_CAPACITY` para business capacity.

## Ejemplo de Salida

```
============================================================
=== CONFIGURACIÓN ===
============================================================
Modo: CREATE

Configuración CREATE:
   • Order ID Base: TEST-ORDER-CONTAINER
   • Order ID Start: 1
   • Total mensajes: 3000
   • Order Type: 3
   • Rango: TEST-ORDER-CONTAINER-000001 hasta TEST-ORDER-CONTAINER-003000

Configuración de Queue:
   • Tipo entidad: order
   • Tipo evento: orderCreated
   • Cola SQS: https://sqs.us-west-2.amazonaws.com/...
   • Región: us-west-2
   • Subdomain: soport
   • Business Capacity: ciclos
   • Delay entre mensajes: 0ms

📝 Log de OrderIds: ./generated_order_ids.json
============================================================
```

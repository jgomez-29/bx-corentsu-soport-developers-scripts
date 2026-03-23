# bx-cnsr-finmg-proforma-checkpoints

Script de pruebas de carga para el consumer **bx-cnsr-finmg-proforma-checkpoints**. Envía mensajes `CheckpointEvent` directamente a la cola SQS `queue-finmg-proforma-checkpoints`.

## Descripción

El consumer lee `message.body()`, lo parsea como `MessageSQS` y extrae el JSON string de `CheckpointEvent` desde `messageSQS.getMessage()`. No valida `MessageAttributes` obligatorios, pero se incluyen por consistencia con el resto del ecosistema.

**Estrategia orderId fijo:** todos los mensajes enviados (tanto de plantilla como sintéticos) comparten el mismo `orderId` de prueba. Esto permite que la prueba siempre opere sobre el mismo documento en Mongo, y al terminar solo queda un registro que limpiar.

## Estructura

```
bx-cnsr-finmg-proforma-checkpoints/
  config.py                          # Config general (ambiente, mensajes, orderId, etc.)
  send_message.py                    # Punto de entrada del script
  checkpoint_event_builder.py        # Builder de CheckpointEvent + envelope MessageSQS
  dev/
    config.py                        # QUEUE_NAME + QUEUE_URL para dev
    entities/
      checkpoint-event.json          # Plantilla CheckpointEvent para dev
  qa/
    config.py                        # QUEUE_NAME + QUEUE_URL para qa
    entities/
      checkpoint-event.json          # Plantilla CheckpointEvent para qa
  logs/                              # Logs de ejecución (generados en runtime, en .gitignore)
  README.md
```

## Cola destino

| Ambiente | Cola                              |
|----------|-----------------------------------|
| dev      | `queue-finmg-proforma-checkpoints` |
| qa       | `queue-finmg-proforma-checkpoints` |

## Formato del mensaje (MessageBody → SQS)

```json
{
  "Type": "Notification",
  "MessageId": "<uuid>",
  "Message": "<JSON string de CheckpointEvent>",
  "Timestamp": "<ISO 8601>",
  "MessageAttributes": {
    "channel":             { "Type": "String", "Value": "Legacy" },
    "eventType":           { "Type": "String", "Value": "created or modified" },
    "domain":              { "Type": "String", "Value": "corentsu" },
    "subdomain":           { "Type": "String", "Value": "soport" },
    "businessCapability":  { "Type": "String", "Value": "finmg" },
    "traceId":             { "Type": "String", "Value": "<uuid hex>" },
    "eventId":             { "Type": "String", "Value": "<uuid>" },
    "spanId":              { "Type": "String", "Value": "<hex 16>" },
    "datetime":            { "Type": "String", "Value": "<ISO 8601>" },
    "timestamp":           { "Type": "Number", "Value": "<unix epoch>" }
  }
}
```

## Estructura de CheckpointEvent

| Campo          | Tipo    | Descripción                                              |
|----------------|---------|----------------------------------------------------------|
| `orderId`      | string  | Identificador de la orden (fijo en toda la prueba)       |
| `sellerAccount`| string  | Cuenta del vendedor                                      |
| `owner`        | string  | Propietario del paquete                                  |
| `packageId`    | string  | ID del paquete (varía por mensaje en modo sintético)     |
| `trackingId`   | integer | ID de tracking (varía por índice en modo sintético)      |
| `eventDate`    | string  | Fecha del evento (ISO 8601)                              |
| `eventType`    | string  | `"created or modified"`                                  |
| `eventCode`    | string  | Código de evento (cicla: DL, DLV, DLO, LD, MST, PM, PDP, VP, DM, …) |
| `location`     | string  | Ubicación textual                                        |
| `status`       | string  | Estado del paquete                                       |
| `agencyId`     | string  | ID de agencia                                            |
| `geolocation`  | object  | `{ "coordinates": [lat, lng] }`                          |
| `creationDate` | string  | Fecha de creación (ISO 8601)                             |

## Variables de entorno (`.env` en la raíz del repo)

```dotenv
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=123456789012
```

> Los nombres de la cola (`QUEUE_NAME`) y la URL (`QUEUE_URL`) se construyen en `dev/config.py` y `qa/config.py`. **No van en `.env`**.

## Cómo ejecutar

Desde la raíz del repo:

```bash
python ./bx-cnsr-finmg-proforma-checkpoints/send_message.py
```

O desde la carpeta del caso de uso:

```bash
cd bx-cnsr-finmg-proforma-checkpoints
python send_message.py
```

El script pedirá de forma interactiva:

1. **Ambiente** (`dev` / `qa`) — default: `dev`
2. **Cantidad de mensajes** — default: `10`
3. **orderId de prueba** — default: `stress-load-test` (o el configurado en `config.py`)

Si la terminal **no** es interactiva (CI/pipeline), se usan los valores de `config.py` sin prompts.

## Modos de generación

| Modo | Condición | Descripción |
|------|-----------|-------------|
| **Plantilla** | Existe `dev/entities/checkpoint-event.json` o `qa/entities/...` | N copias del JSON con el `orderId` de la plantilla |
| **Sintético** | No hay plantilla o no se encuentra | N mensajes con `ORDER_ID` de `config.py` como `orderId` fijo; `eventCode` cicla, `packageId` y `trackingId` varían |

## Logs

Cada ejecución genera un archivo en `logs/` con el formato `proforma_checkpoints_YYYYMMDD_HHMMSS.json`:

```json
{
  "timestamp": "2026-03-23T10:00:00.000Z",
  "environment": "dev",
  "queue_url": "https://sqs.us-east-1.amazonaws.com/123456789012/queue-finmg-proforma-checkpoints",
  "order_id": "dev-order-test-001",
  "total": 10,
  "ok_count": 10,
  "error_count": 0,
  "order_ids": ["dev-order-test-001", "dev-order-test-001", "..."]
}
```

Los logs están en `.gitignore` (`**/logs/`) y no se suben al repo.

## Limpieza post-prueba

Al usar el modo sintético o la plantilla, todos los mensajes comparten el mismo `orderId`. Al terminar la prueba, basta con eliminar **un único documento** en Mongo identificado por ese `orderId`.

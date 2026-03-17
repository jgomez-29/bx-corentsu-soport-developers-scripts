# Biller Unitary - Envío a SQS para pruebas de estrés

Script para enviar mensajes directamente a la cola SQS consumida por **biller-unitary** (bx-cnsr-finmg-biller), permitiendo pruebas de estrés sin depender del flujo real (SNS u otro producer).

## Destino

- **Cola SQS:** `queue-finmg-billing-document-request` (mismo nombre en dev y qa; la URL depende de `AWS_REGION` y `AWS_ACCOUNT_ID`).

## Formato del mensaje

El consumer (SQSConsumer) espera el **cuerpo del mensaje** como JSON de **MessageSQS**:

- **Message:** string que a su vez es el JSON de **DteInformation** (identifier, identifierType, account, createBy, society, billing, details, attachments, totalDetail).
- **MessageAttributes:** obligatorios:
  - `channel` (Type: String, Value: p.ej. "WEB")
  - `eventType` (Type: String, Value: p.ej. "billingOrchestrated")

Sin estos atributos el consumer lanza `BusinessException` y elimina el mensaje.

## Variables de entorno

Solo en el archivo **`.env`** en la **raíz del repo** (no en esta carpeta):

```env
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=123456789012
```

## Cómo ejecutar

Desde la raíz del repo Scripts:

```bash
python ./bx-cnsr-finmg-biller/unitary/send_message.py
```

Prompts interactivos (si la terminal es interactiva):

1. **Ambiente:** dev o qa (por defecto según `config.py`).
2. **Cantidad de mensajes a enviar:** número positivo (por defecto 10).

El script genera payloads sintéticos (DteInformation válidos) con identificadores únicos y los envía a la cola. Al final se muestra un resumen (total, exitosos, fallidos) y se guarda un log JSON en `./logs/` con los identifiers enviados.

## Entidad por ambiente

Cada ambiente tiene su **plantilla de entidad** (DteInformation) en:

- **DEV:** `dev/entities/dte-information.json`
- **QA:** `qa/entities/dte-information.json`

Si ese archivo existe, el script lo usa como plantilla: genera N mensajes replicando ese JSON y cambiando solo `identifier` y `transactionId` en cada uno. Así puedes ver y editar qué datos usa cada ambiente (account, billing, details, etc.).

Si no existe el archivo (o `INPUT_FILE` en `config.py` está vacío), el script genera mensajes **sintéticos** con la misma estructura. En la ejecución se muestra si se está usando plantilla o sintéticos.

## Estructura

| Archivo / carpeta   | Qué es                                                                 |
|---------------------|------------------------------------------------------------------------|
| `config.py`         | Config general: ENVIRONMENT, INPUT_FILE, MAX_MESSAGES, BATCH_SIZE, etc. |
| `dev/config.py`     | Config DEV: QUEUE_NAME, QUEUE_URL (con REGION y AWS_ACCOUNT_ID del .env). |
| `qa/config.py`      | Config QA: mismo esquema.                                              |
| `dev/entities/dte-information.json` | Plantilla DteInformation para DEV.                              |
| `qa/entities/dte-information.json`  | Plantilla DteInformation para QA.                              |
| `send_message.py`   | Script principal: carga config, genera payloads (plantilla o sintéticos), envía a SQS. |
| `biller_unitary_builder.py` | Genera DteInformation y construye el envelope MessageSQS.        |
| `README.md`         | Este archivo.                                                          |

## Logs

Cada ejecución genera un archivo en `./logs/` (relativo al directorio del script) con nombre `biller_unitary_YYYYMMDD_HHMMSS.json`, conteniendo timestamp, environment, queue_url, total, ok_count, error_count e identifiers enviados.

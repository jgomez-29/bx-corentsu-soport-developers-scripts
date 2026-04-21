# replicate-invoice – Envío a `queue-finmg-billing-replicated`

Script para enviar mensajes de replicación de facturas a la cola SQS `queue-finmg-billing-replicated`.

---

## Estructura

```
replicate-invoice/
  config.py                          # Config general: ENVIRONMENT, TARGET, MAX_MESSAGES, etc.
  send_message.py                    # Punto de entrada del script
  billing_replicated_builder.py      # Carga los mensajes desde archivo JSON
  dev/
    config.py                        # QUEUE_URL construida con REGION + ACCOUNT_ID + QUEUE_NAME
    entities/
      billing.json                   # Payload(s) de ejemplo para DEV
  qa/
    config.py                        # Igual que dev, apunta a QA
    entities/
      billing.json                   # Payload(s) de ejemplo para QA
  README.md                          # Este archivo
```

---

## Variables de entorno (`.env` en la raíz del repo)

```env
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=123456789012
```

> ⚠️ Nunca subas el archivo `.env` al repositorio.

---

## Configuración del script (`config.py`)

| Variable      | Descripción                                      | Valor por defecto  |
|---------------|--------------------------------------------------|--------------------|
| `ENVIRONMENT` | Ambiente a usar: `dev` o `qa`                    | `"dev"`            |
| `TARGET`      | Destino: `sqs`, `sns` o `both`                   | `"sqs"`            |
| `MAX_MESSAGES`| Cantidad máxima de mensajes a enviar             | `1`                |
| `ENTITY_TYPE` | Tipo de entidad del evento                       | `"billedDocument"`        |
| `EVENT_TYPE`  | Tipo de evento                                   | `"billingToBeReplicated"` |
| `INPUT_FILE`  | Ruta relativa al JSON de entidades (del ambiente)| `"./entities/billing.json"` |

---

## Estructura del mensaje (payload)

```json
{
  "proformaSerie": null,
  "account": "18841006-1-85",
  "billingDate": null,
  "publishDate": null,
  "totalFreight": null,
  "totalRetriesAmount": null,
  "totalExtendedWarrantyAmount": null,
  "totalAmount": null,
  "totalOrders": null,
  "startDate": null,
  "endDate": null,
  "deliveryStatus": null,
  "orderStatus": null,
  "userPublisher": null,
  "billingRequestId": "fa776979-356f-4951-9922-3e3f5104b67c",
  "step": "REPLICATE_INVOICE",
  "nextStep": null,
  "siiFolio": null,
  "orderDetails": null,
  "billingData": {
    "identifier": "1034257044",
    "identifierType": "order",
    "billingType": "16",
    "rut": "18841006-5",
    "name": "Tiare Morales",
    "billingSociety": "1700",
    "siiFolio": "14813",
    "aceptaDocumentUrl": "http://...",
    "amount": 0.0,
    "totalToPay": 0.0,
    "sendTo": {
      "to": ["correo@ejemplo.com"],
      "cc": null
    }
  }
}
```

El archivo `entities/billing.json` puede contener un único objeto JSON o un array de objetos.

---

## Cómo ejecutar

Desde la raíz del repositorio:

```bash
python ./bx-cnsr-finmg-billing-replicated/replicate-invoice/send_message.py
```

Si la terminal es interactiva, el script preguntará:
- **Ambiente** (`dev` / `qa`) — por defecto el valor en `config.py`
- **Destino** (`sqs` / `sns` / `both`) — por defecto `sqs`
- **Cantidad de mensajes** — por defecto `1`

---

## Logs

Cada ejecución genera un archivo JSON en:
```
dev/logs/billing_replicated_<timestamp>.json
qa/logs/billing_replicated_<timestamp>.json
```

Los logs están en `.gitignore` y no se suben al repositorio.

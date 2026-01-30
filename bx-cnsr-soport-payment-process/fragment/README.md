# payment-process-fragment

Envía mensajes **fragment** (masivo) al topic SNS de payment process con `eventType: paymentProcessRequested`.

- **Destino:** SNS topic (nombre en `dev/config.py` y `qa/config.py`: `TOPIC_NAME`).
- **Estructura:** bulkIdentifier, origin, date, notificationEmail, documentsToCreate (array de documentos).

## Variables de entorno

En el archivo `.env` en la raíz del repo solo se usan datos sensibles:

- `AWS_REGION`
- `AWS_ACCOUNT_ID`

El nombre del topic está en `dev/config.py` y `qa/config.py` (`TOPIC_NAME`).

## Cómo ejecutar

1. Crear `.env` en la raíz del repo con `AWS_REGION` y `AWS_ACCOUNT_ID`.
2. Desde la raíz del repo:  
   `python ./bx-cnsr-soport-payment-process/payment-process-fragment/send_message.py`
3. O desde esta carpeta:  
   `python send_message.py`
4. Responder los prompts: ambiente (dev/qa), destino (sqs/sns/both), cantidad de mensajes.

## Estructura

- `config.py` – Config general (ENVIRONMENT, TARGET, MAX_MESSAGES, etc.).
- `dev/config.py`, `qa/config.py` – REGION y AWS_ACCOUNT_ID desde .env; TOPIC_NAME literal.
- `send_message.py` – Script principal (genera mensajes y publica a SNS).
- `payment_process_fragment_builder.py` – Genera payloads fragment (documentsToCreate) y construye el envelope para SNS.

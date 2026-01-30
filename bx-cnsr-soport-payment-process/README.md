# bx-cnsr-soport-payment-process

Carpeta principal para scripts que envían mensajes al **topic SNS de payment process**.

**Por qué no hay `send_message.py` en esta carpeta (la “base”):**  
Aquí hay **dos casos de uso** (unitary y fragment). Cada uno tiene su **propia subcarpeta** con la **misma estructura** que `bx-cnsr-soport-orders-consolidation`: dentro de cada subcarpeta están `send_message.py`, `config.py`, `*_builder.py`, `dev/`, `qa/`. El script a ejecutar está **dentro** de `unitary/` o de `fragment/`, no en la raíz de payment-process.

## Estructura (dónde está cada cosa)

```
bx-cnsr-soport-payment-process/     ← solo README y subcarpetas (no hay send_message aquí)
├── README.md
├── unitary/                         ← caso de uso 1: mensajes unitarios
│   ├── config.py
│   ├── send_message.py               ← ejecutar este para unitary
│   ├── payment_process_unitary_builder.py
│   ├── dev/
│   │   ├── config.py
│   │   └── entities/
│   └── qa/
│       ├── config.py
│       └── entities/
└── fragment/                        ← caso de uso 2: mensajes fragment/masivo
    ├── config.py
    ├── send_message.py               ← ejecutar este para fragment
    ├── payment_process_fragment_builder.py
    ├── dev/
    │   ├── config.py
    │   └── entities/
    └── qa/
        ├── config.py
        └── entities/
```

Comparación con **orders-consolidation** (un solo caso de uso):

```
bx-cnsr-soport-orders-consolidation/  ← un solo caso, send_message está aquí en la base
├── config.py
├── send_message.py
├── order_builder.py
├── dev/
└── qa/
```

## Subcarpetas (casos de uso)

| Subcarpeta | eventType | Descripción |
|------------|-----------|-------------|
| **unitary/** | paymentProcessUnitary | Mensajes unitarios (un documento por mensaje). |
| **fragment/** | paymentProcessRequested | Mensajes fragment/masivo (array documentsToCreate). |

## Variables de entorno

En la raíz del repo, archivo `.env`: solo `AWS_REGION` y `AWS_ACCOUNT_ID`. Los nombres de topic están en `dev/config.py` y `qa/config.py` de cada subcarpeta (`unitary` o `fragment`).

## Cómo ejecutar

Desde la raíz del repo:

```bash
# Mensajes unitarios
python ./bx-cnsr-soport-payment-process/unitary/send_message.py

# Mensajes fragment/masivo
python ./bx-cnsr-soport-payment-process/fragment/send_message.py
```

O entrando en cada subcarpeta y ejecutando desde ahí:

```bash
cd bx-cnsr-soport-payment-process/unitary
python send_message.py
```

Los prompts piden ambiente (dev/qa), destino (sqs/sns/both) y cantidad de mensajes.

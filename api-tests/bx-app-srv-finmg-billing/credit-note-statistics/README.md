# credit-note-statistics – Prueba de carga HTTP

Script para simular múltiples llamadas al endpoint `GET /finmg/app-srv/billing/v1/credit-note-requests/{request_id}/statistics`. El `request_id` es configurable por prompt al ejecutar.

## Estructura

```
credit-note-statistics/
├── config.py         # Defaults: ENVIRONMENT, REQUEST_ID, TOTAL_REQUESTS, DURATION_SECONDS
├── run.py            # Punto de entrada: prompts, loop de requests, logs
├── dev/
│   └── config.py     # BASE_URL y ENDPOINT_TEMPLATE para dev
├── qa/
│   └── config.py     # BASE_URL y ENDPOINT_TEMPLATE para qa (stage)
├── services/
│   └── http_client.py # GET helper con timing, verify=False
└── logs/             # Logs JSON por ejecución (auto-generado, ignorado por git)
```

## Ambientes

| Ambiente | URL base |
|----------|----------|
| `dev` | `https://bx-app-srv-finmg-billings.dev.blueexpress.tech` |
| `qa` | `https://bx-app-srv-finmg-billings.stg.blueexpress.tech` |

## Variables de entorno

Este script **no requiere variables en `.env`**.

## Cómo ejecutar

```bash
python ./api-tests/bx-app-srv-finmg-billing/credit-note-statistics/run.py
```

## Flujo de prompts

```
--- Configuración de prueba de carga ---

Ambiente (dev / qa) [qa]:
Request ID del bulk (UUID) [b1b42bfa-ecac-4162-8eb5-10aeefa6b4ba]:
Cantidad de requests a enviar [10]:
Duración total en segundos [0, 0 = sin límite]:
¿Confirmar ejecución? [y/N]:
```

El `REQUEST_ID` por defecto se puede cambiar permanentemente en `config.py`.

## URL construida

```
https://bx-app-srv-finmg-billings.stg.blueexpress.tech
  /finmg/app-srv/billing/v1/credit-note-requests/{request_id}/statistics
```

## Salida en terminal

```
  [ 1/10]  200  OK     201 ms
  [ 2/10]  200  OK     198 ms
  ...
───────────────────────────────────────────────────────
  10 OK  |  0 ERROR  |  Promedio: 205 ms  |  Total: 2.1s
  Log guardado en: logs/credit_note_statistics_20260317_143025.json
```

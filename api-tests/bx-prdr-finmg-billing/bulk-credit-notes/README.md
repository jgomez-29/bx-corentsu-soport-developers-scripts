# bulk-credit-notes – Prueba de carga HTTP

Script para simular múltiples llamadas al endpoint `POST /finmg/prdr/billing/v1/bulk-credit-notes`, similar a JMeter. Envía N requests distribuidos en T segundos, muestra progreso en tiempo real y guarda un log JSON con los resultados.

## Estructura

```
bulk-credit-notes/
├── config.py                  # Defaults: ENVIRONMENT, BULK_ID, ELEMENTS_COUNT, TOTAL_REQUESTS, DURATION_SECONDS
├── credit_note_builder.py     # Construye el body con N elementos
├── run.py                     # Punto de entrada: prompts, loop de requests, logs
├── dev/
│   └── config.py              # BASE_URL y FULL_URL para dev
├── qa/
│   └── config.py              # BASE_URL y FULL_URL para qa
├── services/
│   └── http_client.py         # POST helper con timing, verify=False (SSL privado)
└── logs/                      # Logs JSON por ejecución (auto-generado, ignorado por git)
```

## Variables de entorno

Este script **no requiere variables en `.env`** — no tiene datos sensibles. Las URLs están directamente en `dev/config.py` y `qa/config.py`.

## Cómo ejecutar

```bash
python ./api-tests/bx-prdr-finmg-billing/bulk-credit-notes/run.py
```

El script pedirá por terminal:

| Prompt | Descripción | Default en config.py |
|--------|-------------|----------------------|
| Ambiente | `dev` o `qa` | `qa` |
| Cantidad de requests | Número total de requests a enviar | `10` |
| Duración total (segundos) | El delay entre requests se calcula como `T / N` | `60` |
| Confirmación | `y/N` antes de ejecutar | `N` |

## Ejemplo de salida

```
--- Configuración de prueba de carga ---

Ambiente (dev / qa) [qa]: qa
Cantidad de requests a enviar [10]: 5
Duración total en segundos [60]: 30
¿Confirmar ejecución? [y/N]: y

  Ambiente       : qa
  URL            : http://soport.qa.blue.private/finmg/prdr/billing/v1/bulk-credit-notes
  Requests       : 5
  Duración       : 30s  →  delay entre requests: 7.50s
  Elementos/body : 500
  bulkId         : 268d0a1d-8b96-4667-8e2f-d7e42cbbb9c3

¿Confirmar ejecución? [y/N]: y

  [1/5]  200  OK     312 ms
  [2/5]  200  OK     289 ms
  [3/5]  500  ERROR  1204 ms
  [4/5]  200  OK     301 ms
  [5/5]  200  OK     295 ms

───────────────────────────────────────────────────────
  4 OK  |  1 ERROR  |  Promedio: 480 ms  |  Total: 31.3s
  Log guardado en: logs/bulk_credit_notes_20260317_143022.json
```

## Body del request

```json
{
  "bulkId": "268d0a1d-8b96-4667-8e2f-d7e42cbbb9c3",
  "elements": [
    {
      "salesforceId": "johann",
      "account": "123-12-1",
      "date": "2025-01-15T10:00:00.000Z",
      "amount": 1234,
      "identifier": "OS123456",
      "identifierType": "order",
      "rut": "12345678-9"
    }
    // ... 499 elementos más (todos idénticos)
  ]
}
```

El `bulkId` y la cantidad de elementos se configuran en `config.py` (`BULK_ID` y `ELEMENTS_COUNT`).

## Log JSON generado

Cada ejecución genera un archivo `logs/bulk_credit_notes_<timestamp>.json`:

```json
{
  "environment": "qa",
  "url": "http://soport.qa.blue.private/finmg/prdr/billing/v1/bulk-credit-notes",
  "total_requests": 5,
  "duration_seconds": 30,
  "elements_per_request": 500,
  "bulk_id": "268d0a1d-8b96-4667-8e2f-d7e42cbbb9c3",
  "summary": {
    "ok": 4,
    "error": 1,
    "avg_elapsed_ms": 480,
    "total_elapsed_seconds": 31.3
  },
  "results": [
    {
      "request_num": 1,
      "status": "OK",
      "status_code": 200,
      "elapsed_ms": 312,
      "reason": "HTTP 200",
      "timestamp": "2026-03-17T14:30:22.123456+00:00"
    }
  ]
}
```

### Posibles valores de `status`

| Status | Descripción |
|--------|-------------|
| `OK` | El servidor respondió con HTTP 2xx |
| `ERROR` | HTTP 4xx/5xx, timeout o error de conexión |

## Configuración sin prompts (CI / pipeline)

Si la terminal no es interactiva (`sys.stdin.isatty() == False`), el script usa directamente los valores de `config.py` sin pedir input.

Para ajustar los defaults, editar `config.py`:

```python
ENVIRONMENT = "qa"
TOTAL_REQUESTS = 10
DURATION_SECONDS = 60
ELEMENTS_COUNT = 500
```

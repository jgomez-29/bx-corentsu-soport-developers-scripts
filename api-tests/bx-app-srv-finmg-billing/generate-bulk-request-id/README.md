# generate-bulk-request-id – Prueba de carga HTTP

Script para simular múltiples llamadas al endpoint `POST /finmg/billing/bff/v1/generate-bulk-request-id`. El `fileName` en el body es dinámico por request, equivalente a las funciones JMeter `__time`, `__threadNum` y `__Random`.

## Estructura

```
generate-bulk-request-id/
├── config.py            # Defaults: ENVIRONMENT, TOTAL_REQUESTS, DURATION_SECONDS
├── request_builder.py   # Genera el body con fileName único por request
├── run.py               # Punto de entrada: prompts, loop de requests, logs
├── dev/
│   └── config.py        # BASE_URL y FULL_URL para dev
├── qa/
│   └── config.py        # BASE_URL y FULL_URL para qa (stage)
├── services/
│   └── http_client.py   # POST helper con timing, verify=False
└── logs/                # Logs JSON por ejecución (auto-generado, ignorado por git)
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
python ./api-tests/bx-app-srv-finmg-billing/generate-bulk-request-id/run.py
```

## Flujo de prompts

```
--- Configuración de prueba de carga ---

Ambiente (dev / qa) [qa]:
Cantidad de requests a enviar [10]:
Duración total en segundos [0, 0 = sin límite]:
¿Confirmar ejecución? [y/N]:
```

## Body del request (dinámico por request)

Equivalencias JMeter → Python:

| JMeter | Python |
|--------|--------|
| `${__time(yyyyMMddHHmmss)}` | `datetime.now().strftime("%Y%m%d%H%M%S")` |
| `${__threadNum}` | número secuencial del request |
| `${__Random(1,10000)}` | `random.randint(1, 10000)` |

Ejemplo de body generado:
```json
{
  "fileName": "notas_credito_20260317143022_5_7421.xlsx"
}
```

## Salida en terminal

```
  [ 1/10]  200  OK     312 ms  notas_credito_20260317143022_1_4312.xlsx
  [ 2/10]  200  OK     289 ms  notas_credito_20260317143022_2_9871.xlsx
  ...
───────────────────────────────────────────────────────
  10 OK  |  0 ERROR  |  Promedio: 301 ms  |  Total: 3.1s
  Log guardado en: logs/generate_bulk_request_id_20260317_143025.json
```

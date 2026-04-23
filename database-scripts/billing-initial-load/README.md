# billing-initial-load

Script Python de carga inicial para marcar órdenes de servicio (OS) como facturadas
en el nuevo core de facturación, replicando la lógica del consumer `orders-consolidation`.

---

## ¿Qué hace?

1. Itera día a día un rango de fechas sobre la colección `orders` de MongoDB.
2. Para cada día obtiene un cursor de OS con `taxDocument` presente y `billing.status != "BILLED"`.
3. Consulta al legado Oracle en lotes (DCBT + OSER) para obtener número de proforma y costos.
4. Resuelve o crea el documento de proforma en MongoDB (`proformas` + `proformaRequests`).
5. Actualiza `orders.billing` con los datos construidos (bulk_write).
6. Crea el documento de invoice en MongoDB (`invoices`) si no existe.
7. Genera un log JSON detallado por ejecución.

---

## Estructura

```
billing-initial-load/
├── config.py                         # Parámetros de ejecución (os.getenv)
├── run.py                            # Orquestador principal
├── extract_log.py                    # Utilidad: extrae proformaSeries, siiFolios, cuentas y DCBT desde un log
├── entities/
│   └── order.py                      # Builders: billing, proforma, proformaRequest, invoice
├── repositories/
│   ├── legacy_repository.py          # Consultas Oracle batch (DCBT, OSER, findProformaData)
│   ├── order_repository.py           # Cursor emissionDate + bulk_write billing
│   ├── proforma_repository.py        # Find by accounts + save
│   ├── proforma_request_repository.py
│   └── invoice_repository.py         # Batch check siiFolios + insert_many
├── services/
│   └── billing_service.py            # Orquesta todos los escenarios (1–5)
├── logs/                             # Generados automáticamente (ignorados por git)
└── README.md
```

---

## Variables de entorno

Crear el archivo `.env` en la **raíz del repositorio** (nunca versionarlo):

```env
# MongoDB
MONGO_URI=mongodb+srv://usuario:contraseña@host/?retryWrites=true&w=majority
MONGO_DATABASE=nombre_base_de_datos

# Oracle (Legado) — formato Easy Connect
ORACLE_DSN=//host:puerto/servicio
ORACLE_USER=usuario_oracle
ORACLE_PASSWORD=contraseña_oracle
```

> El `ORACLE_DSN` debe usar formato Easy Connect (`//host:puerto/servicio`). El cliente
> agrega automáticamente el `//` si se omite, pero no acepta el formato JDBC (`jdbc:oracle:thin:@`).

---

## Prerrequisito: índice `emissionDate`

El script usa `emissionDate` como campo de filtro principal. Verificar que exista el índice:

```js
db.orders.getIndexes()
// Debe incluir: { "emissionDate": 1 }
```

Si no existe, crearlo antes de ejecutar en producción:

```js
db.orders.createIndex({ "emissionDate": 1 })
```

---

## Cómo ejecutar

```bash
python ./database-scripts/billing-initial-load/run.py
```

### Flujo interactivo — fechas configuradas en config.py

Si `config.py` tiene fechas definidas, el script pregunta primero si usarlas:

```
=== billing-initial-load ===

  Rango configurado: 2026-01-01 → 2026-02-01
¿Usar el rango de fechas configurado? [S/n]: n
¿Fecha de inicio? (YYYY-MM-DD) [YYYY-MM-DD]: 2026-03-01
¿Fecha de término? (YYYY-MM-DD) [YYYY-MM-DD]: 2026-04-01
¿Activar modo DRY_RUN? [S/n]: s
¿Límite DRY_RUN (registros por día, 0 = sin límite)? [100]: 0

=================================================================
=== RESUMEN INICIAL: billing-initial-load ===
=================================================================
  Rango         : 2026-03-01 → 2026-04-01 (31 días)
  Modo          : DRY_RUN (sin escrituras)
  Tamaño lote   : 1000 OS
  ...
=================================================================

[Día 1/31] (3%) 2026-03-01 → 2026-03-02
  OS candidatas del día : 4823
  Lote 1 | 1000/4823 OS (21%) | 980 actualizadas | 0 errores | 45.2 OS/s
  Lote 2 | 2000/4823 OS (41%) | 1950 actualizadas | 0 errores | 47.8 OS/s
  → 4823/4823 OS procesadas (100%) | 4780 actualizadas

[Día 2/31] (6%) 2026-03-02 → 2026-03-03
  ...

=== RESUMEN FINAL ===
  Días procesados         : 31
  ...
```

Si no hay fechas configuradas, las solicita directamente.

### Flujo interactivo — modo real

```
¿Activar modo DRY_RUN? [S/n]: n

⚠  Modo REAL: se realizarán escrituras en MongoDB.
¿Confirmar ejecución? [s/N]: s
```

---

## Utilidad: extract_log.py

Extrae datos de un log generado por el script y crea una carpeta con archivos de texto:

```bash
python ./database-scripts/billing-initial-load/extract_log.py
```

Genera en `logs/<nombre-del-log>/`:

| Archivo | Contenido |
|---|---|
| `proforma_series.txt` | proformaSeries únicas, ordenadas |
| `sii_folios.txt` | siiFolios únicos, ordenados |
| `accounts.txt` | Cuentas únicas, ordenadas |
| `dcbt_nmr_fac_pf.txt` | Números de proforma Oracle únicos, ordenados |

---

## Log JSON

Cada ejecución genera un archivo en `logs/`:

```
logs/billing-initial-load_20260110_143200.json
```

### Estados posibles en `results[].status`

| Status | Descripción |
|---|---|
| `UPDATED` | billing actualizado con proformaId y proformaSerie |
| `UPDATED_WITHOUT_PROFORMA` | billing actualizado sin proformaId (legado no retornó DCBT) |
| `SKIPPED_ALREADY_BILLED` | OS ya tenía `billing.status = "BILLED"` |
| `SKIPPED_NO_TAX_DOCUMENT` | OS sin `taxDocument` |
| `ERROR` | Error inesperado al procesar la OS |
| `DRY_RUN` | Modo DRY_RUN activo — cambios simulados sin escritura |

### Estados posibles en `results[].proforma_action`

| proforma_action | Descripción |
|---|---|
| `FOUND` | Proforma ya existía en MongoDB — se reutiliza |
| `CREATED` | Proforma no estaba en MongoDB pero sí en Oracle — se crea |
| `SKIPPED` | Oracle no retornó `DCBT_NMR_FAC_PF` para esa OS |

### Estados posibles en `results[].invoice_action`

| invoice_action | Descripción |
|---|---|
| `CREATED` | Invoice creado nuevo |
| `FOUND` | Ya existía un invoice con ese `siiFolio` |
| `SKIPPED` | OS skipeada antes de llegar a la lógica de invoice |

### Ejemplo de entrada en `results` (DRY_RUN con proforma CREATED)

```json
{
  "orderId": "ABC123",
  "referenceOrder": "9876543",
  "emissionDate": "2026-01-01T00:00:00+00:00",
  "account": "96801150-11-8",
  "dcbt_nmr_fac_pf": "12345",
  "proforma_action": "CREATED",
  "invoice_action": "CREATED",
  "billing_applied": {
    "siiFolio": "F001",
    "status": "BILLED",
    "billingDate": "2026-01-01T10:00:00",
    "proformaId": "dry_run_id",
    "proformaSerie": "PRO_BELX_202601_12345",
    "detail": { "retries": 0, "additionalCharges": 0 }
  },
  "proforma_created": {
    "account": "96801150-11-8",
    "proformaSerie": "PRO_BELX_202601_12345",
    "serviceCharges": { "freight": 5000, "extendedWarranty": 0, "retries": 0, "total": 5000 },
    "orderTypeCounters": {
      "multiOrderParentCounter": 0,
      "multiOrderChildCounter": 0,
      "multiPackageOrderCounter": 0,
      "singleOrderCounter": 1
    }
  },
  "invoice_created": {
    "siiFolio": "F001",
    "isLegacy": true,
    "totalDetail": {
      "taxableSubTotal": 5000, "taxRate": 19, "tax": 950, "total": 5950, "totalToPay": 5950,
      "exemptSubtotal": 0, "discount": 0, "cashAdjustment": 0
    }
  },
  "status": "DRY_RUN",
  "reason": "Modo DRY_RUN activo"
}
```

---

## Notas técnicas

- Consultas Oracle usan `IN` con bind variables (máx. 1000 items).
- Lookup de proformas por accounts únicos del lote (evita regex 1:1 por OS).
- `bulk_write(ordered=False)` para maximizar throughput en MongoDB.
- DRY_RUN = True por defecto en `config.py` para evitar escrituras accidentales.
- En DRY_RUN los conteos de `proformas_created` pueden estar inflados entre lotes (las proformas simuladas no se persisten en MongoDB).
- Logs generados en `logs/` (ignorados por git via `.gitignore`).
- El IVA aplicado en `totalDetail` de invoices es fijo al 19% (tasa Chile).

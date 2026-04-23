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
├── entities/
│   └── order.py                      # Builders: billing, proforma, invoice + generate_part1
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
MONGO_URI=mongodb://usuario:contraseña@host:27017
MONGO_DATABASE=nombre_base_de_datos

# Oracle (Legado)
ORACLE_DSN=host:puerto/servicio
ORACLE_USER=usuario_oracle
ORACLE_PASSWORD=contraseña_oracle
```

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

### Flujo interactivo (modo DRY_RUN)

```
=== billing-initial-load ===

¿Fecha de inicio? (YYYY-MM-DD) []: 2026-01-01
¿Fecha de término? (YYYY-MM-DD) []: 2026-01-05
¿Activar modo DRY_RUN? [S/n]: s
¿Límite DRY_RUN (registros por día, 0 = sin límite)? [100]: 50

=== RESUMEN INICIAL: billing-initial-load ===
  Rango         : 2026-01-01 → 2026-01-05 (4 días)
  Modo          : DRY_RUN (sin escrituras)
  Límite/día    : 50 registros
  Tamaño lote   : 1000 OS
  ...

[Día 1/4] 2026-01-01 → 2026-01-02
  Lote 1 | 50 OS | 48 actualizadas | 0 errores | 12.3 OS/s
  → 50 OS procesadas | 48 actualizadas (límite DRY_RUN 50)

...

=== RESUMEN FINAL ===
  Días procesados         : 4
  OS candidatas           : 198
  Actualizadas (c/proforma): 185
  Actualizadas (s/proforma): 8
  Skipped (ya BILLED)     : 0
  Skipped (sin taxDoc)    : 5
  Errores                 : 0
  Proformas creadas       : 12
  Invoices creadas        : 193
  (Modo DRY_RUN: sin escrituras)
  Throughput              : 11.4 OS/s
  Tiempo total            : 00:00:17
```

### Ejecutar en modo real

```
¿Activar modo DRY_RUN? [S/n]: n

⚠  Modo REAL: se realizarán escrituras en MongoDB.
¿Confirmar ejecución? [s/N]: s
```

---

## Log JSON

Cada ejecución genera un archivo en `logs/`:

```
logs/billing-initial-load_20260110_143200.json
```

### Estados posibles en `results[].status`

| Status                      | Descripción                                                   |
|-----------------------------|---------------------------------------------------------------|
| `UPDATED`                   | billing actualizado con proformaId y proformaSerie            |
| `UPDATED_WITHOUT_PROFORMA`  | billing actualizado sin proformaId (legado no retornó DCBT)  |
| `SKIPPED_ALREADY_BILLED`    | OS ya tenía `billing.status = "BILLED"`                      |
| `SKIPPED_NO_TAX_DOCUMENT`   | OS sin `taxDocument`                                          |
| `ERROR`                     | Error inesperado al procesar la OS                            |
| `DRY_RUN`                   | Modo DRY_RUN activo — cambios simulados sin escritura         |

### Ejemplo de entrada en `results`

```json
{
  "orderId": "ABC123",
  "referenceOrder": "9876543",
  "emissionDate": "2026-01-01T00:00:00+00:00",
  "dcbt_nmr_fac_pf": "12345",
  "proforma_action": "CREATED",
  "invoice_action": "CREATED",
  "billing_applied": {
    "siiFolio": "F001",
    "status": "BILLED",
    "billingDate": "2026-01-01T10:00:00",
    "proformaId": "6639abc...",
    "proformaSerie": "PRO_BELX_202601_12345",
    "detail": { "retries": 0, "additionalCharges": 0 }
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
- Logs generados en `logs/` (ignorados por git via `.gitignore`).

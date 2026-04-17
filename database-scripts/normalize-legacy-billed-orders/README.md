# normalize-legacy-billed-orders

Script de carga inicial para marcar en MongoDB las órdenes de servicio (OS) que fueron
facturadas en el sistema legado SAM (Oracle), pero que no están marcadas como facturadas
en el nuevo core de facturación.

---

## Descripción

Consulta la colección `orders` en MongoDB buscando OS sin `billing.status = "BILLED"`
cuya `emissionDate` esté en el rango indicado, luego verifica en la tabla `DCBT` de
Oracle legado si existe un número de proforma (`DCBT_NMR_FAC_PF`) para cada OS.
Las OS encontradas en Oracle se actualizan en MongoDB con `billing.proformaId` y
`billing.status = "BILLED"`.

Utiliza **keyset pagination por `_id`** para paginar MongoDB en lotes de hasta 1000
documentos, y consulta Oracle con `IN (:1, :2, ...)` para el mismo lote, minimizando
la cantidad de round-trips al sistema legado.

---

## Estructura

```
normalize-legacy-billed-orders/
├── config.py                     # Configuración: variables de entorno y parámetros
├── run.py                        # Punto de entrada principal
├── entities/
│   └── order.py                  # Estructura del documento OS + build_billing_update()
├── repositories/
│   └── order_repository.py       # COLLECTION_NAME, find_unbilled_orders_batch, bulk_update_billing
├── services/
│   └── oracle_client.py          # OracleConnection, fetch_proforma_ids_batch
├── logs/                         # Logs JSON generados en cada ejecución (gitignored)
└── README.md                     # Este archivo
```

---

## Variables de entorno

En el archivo **`.env`** de la raíz del repositorio (nunca en código fuente):

```env
# MongoDB
MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/
MONGO_DATABASE=nombre-base-datos

# Oracle legado
ORACLE_DSN=host:1521/service_name
ORACLE_USER=usuario_oracle
ORACLE_PASSWORD=contraseña_oracle
```

---

## Cómo ejecutar

```bash
python ./database-scripts/normalize-legacy-billed-orders/run.py
```

El script solicita interactivamente:
1. **Fecha de inicio** (formato `YYYY-MM-DD`)
2. **Fecha de término** (formato `YYYY-MM-DD`)
3. **Modo DRY_RUN** (por defecto `Y` — seguro, no modifica MongoDB)
4. **Confirmación** antes de ejecutar en modo REAL

### Modo no interactivo (CI/pipeline)

Cuando `sys.stdin.isatty()` es `False`, se usan los valores de `config.py`:

```python
# config.py
DRY_RUN   = False
DATE_FROM = "2026-01-01"
DATE_TO   = "2026-01-31"
```

---

## Flujo de ejecución

```
MongoDB query (rango completo, sort _id ASC, limit 1000)
    └─► Lote de hasta 1000 OS
            ├─► Oracle: SELECT EEVV_NMR_ID, DCBT_NMR_FAC_PF FROM DCBT WHERE EEVV_NMR_ID IN (...)
            │       └─► dict {referenceOrder → proformaId}
            ├─► Clasificar cada OS:
            │       ├── Encontrada en Oracle  → UPDATED (o DRY_RUN)
            │       ├── No encontrada          → NOT_IN_LEGACY
            │       └── Ya tenía billing BILLED → ALREADY_BILLED (skip)
            ├─► bulk_write UpdateOne × N (solo si DRY_RUN=False)
            └─► last_id = lote[-1]["_id"] → siguiente página
```

---

## Statuses del log JSON

| Status | Descripción |
|--------|-------------|
| `UPDATED` | OS actualizada exitosamente en MongoDB (modo REAL) |
| `DRY_RUN` | OS que se habría actualizado (modo DRY_RUN) |
| `ALREADY_BILLED` | OS ya tenía `billing.status = "BILLED"`, no modificada |
| `NOT_IN_LEGACY` | `referenceOrder` no encontrado en tabla DCBT de Oracle |
| `ERROR` | Error durante consulta Oracle o escritura MongoDB |

---

## Ejemplo de log JSON

```json
{
  "timestamp": "2026-04-15T17:00:00Z",
  "dry_run": true,
  "date_from": "2026-01-01",
  "date_to": "2026-01-31",
  "duration_seconds": 45.3,
  "throughput_per_second": 20.97,
  "total_found": 1200,
  "total_updated": 950,
  "total_already_billed": 100,
  "total_not_in_legacy": 130,
  "total_errors": 20,
  "results": [
    {
      "order_id": "ORD-2026-001234",
      "reference_order": "REF-00098765",
      "emission_date": "2026-01-15 00:00:00+00:00",
      "proforma_id": "PF-000999",
      "status": "DRY_RUN",
      "reason": "proformaId=PF-000999 asignado desde DCBT"
    }
  ]
}
```

---

## Re-ejecución (idempotencia)

El script es seguro de re-ejecutar sobre el mismo rango de fechas:
- OS ya con `billing.status = "BILLED"` se omiten (`ALREADY_BILLED`).
- El filtro `{"billing.status": {"$ne": "BILLED"}}` garantiza que no se sobreescriben datos.
- En una segunda ejecución sobre el mismo rango debe reportar `0 actualizadas`.

---

## Verificación en MongoDB

```javascript
// Debe retornar 0 después de una ejecución exitosa en modo REAL
db.orders.countDocuments({
  emissionDate: { $gte: ISODate("2026-01-01"), $lt: ISODate("2026-02-01") },
  "billing.status": { $ne: "BILLED" }
})
```

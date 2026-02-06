# Notification Resend - Reenvío de Notificaciones

Script para reenviar notificaciones de correo a usuarios, basándose en errores de envío registrados en un CSV.

## Flujo

1. **Lee CSV** (`reports/notification-errors.csv`) → extrae `orderId` (columna `#identifier`)
2. **Consulta MongoDB `orders`** por `orderId` → obtiene `billing.siiFolio` y `buyer.email`
3. **Consulta MongoDB `invoices`** por `{ siiFolio, relatedElements.identifier: orderId }` → obtiene `siiDocumentPath` y `totalDetail.totalToPay`
4. **Llama a la API** de notificaciones con los datos recolectados para enviar el correo

## Estructura

```
notification-resend/
├── config.py                          # Configuración general (defaults para prompts interactivos)
├── entities/
│   └── notification_request.py        # Estructura del payload para la API + builder
├── repositories/
│   ├── order_repository.py            # Colección "orders" (campos y filtros explícitos)
│   └── invoice_repository.py          # Colección "invoices" (campos y filtros explícitos)
├── services/
│   ├── csv_reader.py                  # Lectura de CSV + lectura de JSON de retry
│   └── notification_client.py         # Cliente HTTP para la API de notificaciones
├── reports/
│   └── notification-errors.csv        # CSV de entrada con errores de notificación
├── logs/                              # Logs de ejecución (generados automáticamente)
├── run_resend.py                      # Script orquestador principal
└── README.md
```

## Campos por colección

### orders (soport-orders.orders)
| Campo | Uso |
|-------|-----|
| `orderId` | Filtro de búsqueda |
| `billing.siiFolio` | Para buscar la factura asociada |
| `buyer.email` | Email real del destinatario (modo producción) |

### invoices (soport-orders.invoices)
| Campo | Uso |
|-------|-----|
| `siiFolio` | Filtro de búsqueda |
| `relatedElements.identifier` | Filtro de búsqueda (orderId) |
| `siiDocumentPath` | URL del comprobante → `enlace_comprobante` |
| `totalDetail.totalToPay` | Monto → `monto` |

## Template del correo

| templateData key | Origen |
|------------------|--------|
| `serviceOrderNumber` | `orderId` (del CSV) |
| `enlace_comprobante` | `invoices.siiDocumentPath` |
| `monto` | `invoices.totalDetail.totalToPay` |

## Variables de entorno (.env)

```env
MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/
MONGO_DATABASE=soport-orders
```

## Uso

```bash
python ./database-scripts/notification-resend/run_resend.py
```

El script pide por terminal:

1. **¿Reintentar fallidos?** → Si es sí, lista los logs disponibles para seleccionar
2. **¿Modo DRY_RUN?** → Muestra el email de prueba configurado
3. **Email destino** → Permite cambiarlo para esta ejecución
4. **Cantidad de registros** → Limitar para probar con pocos
5. **Confirmación** → Resumen + doble check antes de ejecutar

### Modos

| Modo | Email destino | Registros |
|------|--------------|-----------|
| DRY_RUN + límite | Email de prueba (configurable por terminal) | Solo los primeros N |
| DRY_RUN sin límite | Email de prueba | Todos |
| Producción | `buyer.email` real de cada orden | Todos |
| Retry | Según DRY_RUN | Solo los fallidos del log seleccionado |

### Logs

Cada ejecución genera un JSON en `logs/` con:
- Todos los resultados (exitosos y fallidos con motivo)
- Referencia al log origen si es un reintento (`retry_source`)
- Se puede usar como fuente para reintentar solo los fallidos

## Dependencias

- `pymongo` → Conexión a MongoDB
- `requests` → Llamadas HTTP a la API
- `python-dotenv` → Carga de variables de entorno

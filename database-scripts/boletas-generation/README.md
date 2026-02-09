# Boletas Generation - Generación de Boletas desde Excel

Script para consultar API de boletas y actualizar un archivo Excel con los resultados.

## Flujo

1. **Lee Excel de entrada** (en `reports/`) → extrae registros con `HESCode`
2. **Llama API** con `requestId` → obtiene lista de respuestas (éxitos y errores)
3. **Hace match** por `HESCode` entre Excel y API
4. **Genera nuevo Excel** agregando 2 columnas:
   - `BOLETA`: `BTECode` si exitoso, `0` si error o no encontrado
   - `DETALLE_ERRORES`: `errorDetails.message` si existe, sino `status`, vacío si exitoso
5. **Genera log JSON** con detalle por cada registro procesado

## Estructura

```
boletas-generation/
├── config.py                    # Config general: API URL, request ID, archivos
├── run.py                       # Script orquestador principal
├── entities/
│   └── boleta_response.py       # Estructura de la respuesta de la API
├── repositories/
│   └── boletas_api_client.py    # Cliente HTTP para la API
├── services/
│   └── excel_processor.py       # Lectura y escritura de Excel, matching
├── reports/                     # Excel de entrada
│   └── SOPORT BTE - MIRO Flex Laboral Scl Ene26.xlsx
├── output/                      # Excel de salida (generado automáticamente)
└── logs/                        # Logs JSON de ejecución
```

## Requisitos

- Python 3.8+
- Dependencias: `openpyxl`, `requests`, `python-dotenv`
- Variables de entorno en `.env` (raíz del repo):

```env
BOLETAS_API_URL=http://localhost:3000
BOLETAS_REQUEST_ID=YmF0Y2hfMTc3MDIxMTE2MTQzMl8yODZlODlkMC1mYTU3LTQ1ODctOGY5MS0zOTc5YzAyNGM0MWQ=
```

## Uso

```bash
python ./database-scripts/boletas-generation/run.py
```

### Flujo interactivo

1. **DRY_RUN** → ¿Solo preview sin generar Excel? (Y/n)
2. **DRY_RUN_LIMIT** → ¿Cuántos registros mostrar en preview? (0 = todos)
3. Muestra resumen de configuración (API, request ID, archivo entrada)
4. Lee Excel, consulta API, hace match
5. Si no es DRY_RUN: pide confirmación antes de generar el Excel de salida
6. Guarda log JSON con el resultado

## Formato del Excel de entrada

- Debe tener una columna con header que contenga "HES" (ej: `HESCode`, `HES Code`, etc.)
- El script busca automáticamente esta columna
- Se agregan 2 columnas al final del Excel de salida: `BOLETA` y `DETALLE_ERRORES`

## Respuesta de la API

La API retorna una lista de documentos:

### Documento exitoso
```json
{
  "documentToCreate": {
    "HESCode": 176099,
    "BTECode": 59942,
    ...
  },
  "status": "BTE_CREATED"
}
```

### Documento con error
```json
{
  "documentToCreate": {
    "HESCode": 176430,
    "BTECode": null,
    ...
  },
  "status": "BTE_CREATE_ERROR",
  "errorDetails": {
    "message": "communeName: Commune 'ANCUD' does not exist"
  }
}
```

## Manejo de casos

| Caso | BOLETA | DETALLE_ERRORES |
|------|--------|-----------------|
| Exitoso (`status == "BTE_CREATED"`) | `BTECode` | (vacío) |
| Error con `errorDetails.message` | `0` | Mensaje de error |
| Error sin `errorDetails` | `0` | `status` |
| No encontrado en API | `0` | `"NO_ENCONTRADO_EN_API"` |

**Nota:** Si un `HESCode` del Excel no está en la respuesta de la API, se informa en terminal y en el log JSON, y se marca con error.

## Log JSON

Cada ejecución genera un archivo en `logs/` con:

```json
{
  "timestamp": "2026-02-06T...",
  "dry_run": false,
  "api_url": "...",
  "request_id": "...",
  "input_file": "...",
  "output_file": "...",
  "summary": {
    "total_excel_records": 266,
    "total_api_documents": 266,
    "processed": 266,
    "success": 250,
    "errors": 10,
    "not_found": 6
  },
  "results": [
    {
      "hes_code": 176099,
      "boleta": 59942,
      "detalle_errores": "",
      "status": "SUCCESS"
    },
    ...
  ]
}
```

## Estados del log

- `SUCCESS`: Procesado exitosamente con BTECode
- `ERROR`: Error en la API (detalle en `detalle_errores`)
- `NOT_FOUND`: HESCode no encontrado en la respuesta de la API

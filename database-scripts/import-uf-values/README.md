# Import UF Values

Script para importar valores de UF (Unidad de Fomento) desde archivos CSV a MongoDB.

## Estructura

```
import-uf-values/
├── config.py                  # Configuración general
├── run.py                     # Script orquestador principal
├── entities/
│   └── uf_value.py            # Estructura del documento MongoDB
├── repositories/
│   └── uf_value_repository.py # Acceso a colección "uf-values"
├── services/
│   └── csv_parser.py          # Lectura y parseo de CSVs
├── uf-reports/                # Archivos CSV de entrada
│   ├── UF 2025.csv
│   └── UF 2026.csv
└── logs/                      # Logs de ejecución (JSON)
```

## Requisitos

- Python 3.8+
- Dependencias: `pymongo`, `python-dotenv` (opcional)
- Variables de entorno en `.env` (raíz del repo):

```env
MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/
MONGO_DATABASE=soport-orders
```

## Uso

```bash
python ./database-scripts/import-uf-values/run.py
```

### Flujo interactivo

1. **DRY_RUN** → ¿Solo preview sin insertar? (Y/n)
2. **DRY_RUN_LIMIT** → ¿Cuántos registros mostrar en preview? (0 = todos)
3. Muestra resumen de configuración
4. Si no es DRY_RUN: consulta MongoDB por fechas existentes → inserta solo las nuevas
5. Pide confirmación antes de insertar
6. Guarda log JSON con el resultado

### Formato del CSV

```
Día;Ene;Feb;Mar;...;Dic
1;38.419,17;38.381,93;38.663,05;...;39.643,59
```

- Separador: `;`
- Valores: `39.703,50` (punto = miles, coma = decimal)
- Celdas vacías = no hay valor para esa fecha → se ignoran
- El año se extrae del nombre: `UF 2025.csv` → 2025

### Documento MongoDB

```json
{
  "date": "2025-01-01T00:00:00.000Z",
  "value": 38419.17
}
```

- Colección: `uf-values`
- `date`: ISODate con hora en 00:00:00 UTC
- `value`: float con decimales tal cual del CSV

### Manejo de duplicados

Si un registro con la misma fecha ya existe en la DB, **no se reemplaza**. El log JSON reporta las fechas que se omitieron por ya existir.

### Logs

Cada ejecución genera un archivo en `logs/`:

```
logs/import_20260206_150000.json
```

Contiene: estadísticas del CSV, cantidad insertada, fechas omitidas, etc.

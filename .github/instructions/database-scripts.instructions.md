---
# Se aplica a cualquier archivo dentro de database-scripts/ y al cliente MongoDB compartido.
# Los globs cubren cualquier script futuro sin necesidad de actualizar este archivo.
applyTo:
  - "database-scripts/**/run.py"
  - "database-scripts/**/config.py"
  - "database-scripts/**/entities/**"
  - "database-scripts/**/repositories/**"
  - "database-scripts/**/services/**"
  - "common/mongo/**"
---

# Instrucciones al editar database-scripts o common/mongo

## Patrón obligatorio

Cada script dentro de `database-scripts/` sigue esta estructura:

```
database-scripts/<nombre>/
├── config.py              # MONGO_URI y MONGO_DATABASE de os.getenv(), DRY_RUN, rutas
├── run.py                 # Orquestador principal (prompts, lógica, logs)
├── entities/              # Estructura del documento MongoDB
├── repositories/          # Acceso a colecciones (COLLECTION_NAME, funciones de consulta/inserción)
├── services/              # Lógica de negocio (parseo CSV, clientes HTTP, etc.)
├── reports/ o *-reports/  # Archivos de entrada
├── logs/                  # Generados automáticamente, ignorados por git
└── README.md
```

## Reglas al editar

### run.py
- Siempre se llama `run.py` (nunca `run_<nombre>.py` ni `main.py`).
- Resolver raíz del repo buscando `common/` hacia arriba. Agregar a `sys.path`.
- Agregar `script_dir` (directorio del run.py) a `sys.path` para imports locales (los guiones en `database-scripts/` impiden imports por módulo Python).
- Cargar `.env` desde la raíz del repo con `load_dotenv` + fallback manual.
- Incluir prompts interactivos: `prompt_yes_no`, `prompt_int`, `prompt_string`. Saltarlos si `sys.stdin.isatty()` es False.
- Siempre soportar **DRY_RUN** (simula sin tocar DB) y pedir **confirmación** antes de escribir.
- Generar log JSON en `logs/` con array `results` detallado (estructura del dato, status, razón).

### config.py
- `MONGO_URI` y `MONGO_DATABASE` siempre de `os.getenv()`. Nunca hardcodear.
- Incluir `DRY_RUN = True` y `DRY_RUN_LIMIT` como valores por defecto seguros.
- Rutas relativas al script (ej. `"./uf-reports"`, `"./logs"`).

### entities/
- Cada archivo debe tener un docstring claro: nombre de colección, estructura del documento, tipos, ejemplo real.
- Funciones builder que construyen el documento listo para insertar (ej: `build_uf_document(year, month, day, value)`).
- Usar `datetime` con `timezone.utc` para fechas (hora en 00:00:00 UTC).

### repositories/
- Constante `COLLECTION_NAME` definida en el archivo (no en config.py).
- Funciones puras: reciben la colección de pymongo y retornan datos.
- Para inserciones masivas: `insert_many(documents, ordered=False)`.
- Para verificación de duplicados: consultar claves existentes antes de insertar.

### services/
- Lógica desacoplada: parseo de CSV, clientes HTTP, transformaciones.
- Al leer CSV: usar `encoding="utf-8-sig"` (maneja BOM de Excel en Windows).
- Al llamar APIs internas con SSL privado: `verify=False` + `urllib3.disable_warnings`.

### common/mongo/
- `MongoConnection` es un context manager reutilizable. No crear clientes MongoDB ad-hoc.
- No modificar la interfaz sin verificar compatibilidad con todos los scripts existentes.
- Si necesitas nueva funcionalidad de conexión, extender sin romper el `__enter__`/`__exit__` actual.

## Scripts de referencia

| Tipo de operación | Script de referencia | Descripción |
|---|---|---|
| Importar datos CSV → MongoDB | `database-scripts/import-uf-values/` | Lee CSVs, parsea, verifica duplicados, bulk insert |
| Consultar MongoDB + llamar API | `database-scripts/notification-resend/` | Lee CSV de entrada, consulta orders/invoices, envía notificaciones |

Al crear un script nuevo, **copiar el flujo del script de referencia más cercano** y adaptar entidades, repositorios y servicios.

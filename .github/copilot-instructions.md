# Instrucciones para Copilot – Scripts de Operaciones

## 1. Resumen del proyecto

- **Qué es:** Repositorio de scripts Python para operaciones de backend: envío de mensajes a SQS/SNS (AWS) y scripts de base de datos (MongoDB, etc.).
- **Para quién:** Desarrolladores que necesitan probar, cargar datos o ejecutar operaciones puntuales contra servicios de backend.
- **Características:** Config por ambiente (dev/qa) en scripts SQS/SNS, prompts interactivos al ejecutar, código común en `common/`, sin datos sensibles en el repo (solo en `.env`).
- **Dos tipos de scripts:**
  - **Scripts SQS/SNS** (`bx-cnsr-*`): envío de mensajes a colas/topics AWS.
  - **Scripts de base de datos** (`database-scripts/`): operaciones contra MongoDB u otros datastores.

## 2. Stack y dependencias

- **Lenguaje:** Python 3.
- **Dependencias:** `boto3`, `pymongo`, `requests`, `python-dotenv` (ver `requirements.txt`).
- **Entorno:** Variables de entorno desde `.env` en la raíz; fallback de carga manual si `python-dotenv` no está instalado.

## 3. Estándares de código

- Usar **Path** de `pathlib` para rutas; no hardcodear rutas absolutas.
- Imports: estándar primero, luego terceros, luego `common/` (tras añadir repo root a `sys.path`).
- Comentarios y mensajes al usuario en **español**; nombres de variables/funciones en inglés.
- Validar entradas (ambiente, TARGET, cantidad de mensajes) y lanzar `ValueError` con mensaje claro si algo falla.
- No duplicar lógica de SQS/SNS: usar siempre `common.sqs` y `common.sns`.

## 4. Estructura del repo

- **`common/`** – Código compartido (publicadores SQS/SNS, message builder, conexión MongoDB). No tocar sin alinear con todos los casos de uso.
  - `common/sqs/` – Publicador SQS y message builder.
  - `common/sns/` – Publicador SNS.
  - `common/mongo/` – Cliente MongoDB reutilizable (`MongoConnection`, context manager).
- **Carpetas SQS/SNS** (ej. `bx-cnsr-finmg-billing/proforma-detailed/`). Cada una debe tener la estructura indicada en la sección 5.
- **`database-scripts/`** – Scripts de base de datos. Cada sub-carpeta es un script independiente con la estructura indicada en la sección 5b.

## 5. Estructura obligatoria de un nuevo caso de uso (SQS/SNS)

Al **añadir** un nuevo script/caso de uso, crear exactamente:

```
<nombre-caso>/
  config.py                       # Config GENERAL: ENVIRONMENT, TARGET, ENTITY_TYPE, EVENT_TYPE, MAX_MESSAGES, BATCH_SIZE, INPUT_FILE, LOGS_DIR, etc.
  send_message.py                  # Script principal (nombre convencional; según TARGET envía a SQS, SNS o ambos)
  <entidad>_builder.py             # Carga entidades y construye envelopes (compatible con MessageBuilder)
  dev/
    config.py                     # REGION, AWS_ACCOUNT_ID desde os.getenv; QUEUE_NAME, TOPIC_NAME literales; construir QUEUE_URL y TOPIC_ARN
    entities/                     # JSON de entrada para dev
    logs/                          # Opcional
  qa/
    config.py                     # Igual que dev; nombres de cola/topic de QA si difieren
    entities/
    logs/
  README.md                        # Uso, variables de entorno, nombres en config (ver sección 7)
```

## 5b. Estructura obligatoria de un nuevo database-script

Al **añadir** un nuevo script dentro de `database-scripts/`, crear exactamente:

```
database-scripts/<nombre-script>/
  config.py                        # Config general: MONGO_URI/MONGO_DATABASE de os.getenv, DRY_RUN, DRY_RUN_LIMIT, rutas, etc.
  run.py                           # Script orquestador principal (siempre se llama run.py)
  entities/
    __init__.py
    <entidad>.py                   # Estructura del documento MongoDB (docstring claro con colección, campos, tipos, ejemplo)
  repositories/
    __init__.py
    <entidad>_repository.py        # Acceso a colección: COLLECTION_NAME como constante, funciones de consulta/inserción
  services/
    __init__.py
    <servicio>.py                  # Lógica de negocio: parseo de CSV, clientes HTTP, etc.
  reports/ o <nombre>-reports/     # Archivos de entrada (CSV, JSON, etc.)
  logs/                            # Logs de ejecución (generados automáticamente, ignorados por git)
  README.md                        # Uso, estructura, formato de entrada, documento MongoDB, manejo de errores
```

### Reglas del patrón database-scripts

1. **Punto de entrada**: Siempre `run.py`. Se ejecuta desde la raíz del repo: `python ./database-scripts/<nombre>/run.py`.
2. **Config**: `config.py` lee `MONGO_URI` y `MONGO_DATABASE` desde `os.getenv()` (definidos en `.env` de la raíz). Nunca hardcodear credenciales.
3. **Prompts interactivos**: `run.py` debe preguntar al usuario opciones clave (DRY_RUN, límites, confirmaciones) usando funciones `prompt_yes_no`, `prompt_int`, `prompt_string`. Si no es terminal interactiva (`sys.stdin.isatty() == False`), usar valores por defecto de `config.py`.
4. **DRY_RUN**: Todo script debe soportar modo DRY_RUN que simule la operación sin modificar la base de datos. En este modo se genera un log con status `DRY_RUN`.
5. **Confirmación**: Antes de cualquier operación destructiva o de escritura, pedir confirmación explícita al usuario.
6. **Logs JSON**: Cada ejecución genera un archivo en `logs/` con timestamp. El log debe incluir un array `results` con el detalle de cada registro procesado, incluyendo:
   - La estructura del dato (fecha, valor, campos clave)
   - El status: `INSERTED`, `ALREADY_EXISTS`, `SENT`, `ERROR`, `DRY_RUN`, etc.
   - La razón del resultado
7. **Entities**: Docstring claro con: nombre de colección, estructura del documento, tipos de cada campo, ejemplo real.
8. **Repositories**: Constante `COLLECTION_NAME` definida en el archivo (no en `config.py`). Funciones puras que reciben la colección de pymongo y retornan datos.
9. **Common**: Usar `common/mongo/mongo_client.py` (`MongoConnection`) para conexión. No crear clientes MongoDB ad-hoc.
10. **Resolución de imports**: Como las carpetas `database-scripts/` tienen guiones (no válidos en Python), `run.py` agrega `script_dir` a `sys.path` e importa módulos locales directamente (ej: `from services.csv_parser import ...`).
11. **Bulk operations**: Para inserciones masivas, preferir `insert_many` con `ordered=False`. Para verificación de duplicados, consultar primero las claves existentes.
12. **Encoding CSV**: Usar `encoding="utf-8-sig"` al leer CSVs (maneja BOM de Excel en Windows).

## 6. Reglas de configuración (SQS/SNS)

- **Solo en `.env` (raíz):** `AWS_REGION`, `AWS_ACCOUNT_ID`. No usar variables de entorno para `QUEUE_NAME` ni `TOPIC_NAME`.
- **En `dev/config.py` y `qa/config.py`:**
  - `REGION = os.getenv("AWS_REGION")`, `AWS_ACCOUNT_ID = os.getenv("AWS_ACCOUNT_ID")`.
  - `QUEUE_NAME = "nombre-cola"`, `TOPIC_NAME = None` (o `"nombre-topic"` si SNS) como **literales**.
  - `QUEUE_URL` y `TOPIC_ARN` construidos con `f"https://sqs.{REGION}.amazonaws.com/{AWS_ACCOUNT_ID}/{QUEUE_NAME}"` y análogo para SNS.
- **En `config.py` (raíz del caso de uso):** `ENVIRONMENT`, `TARGET`, `ENTITY_TYPE`, `EVENT_TYPE`, `MAX_MESSAGES` (o `TOTAL_MESSAGES` si aplica), `BATCH_SIZE`, `INPUT_FILE`, `LOGS_DIR`, etc.

## 7. Reglas del script principal (`send_message.py`)

El archivo se llama `send_message.py` por convención histórica; en realidad puede enviar a SQS, SNS o ambos según `TARGET` en config. Es el **único punto de entrada** por caso de uso.

1. Resolver **raíz del repo** subiendo desde `Path(__file__).parent` hasta el directorio que contiene `common/`. Añadir esa ruta a `sys.path` antes de importar `common`.
2. Cargar **`.env`** desde `repo_root / ".env"`: usar `load_dotenv(str(_env_file))` y, si las variables siguen vacías, cargar el archivo manualmente (líneas `KEY=VALUE` no comentadas).
3. Cargar **config en dos niveles:** `config.py` (general) y `{ENVIRONMENT}/config.py` (dev o qa). Si la terminal es interactiva (`sys.stdin.isatty()`), preguntar: ambiente (dev/qa), destino (sqs/sns/both), cantidad de mensajes; si no, usar valores del config.
4. Validar: si faltan `REGION` o `AWS_ACCOUNT_ID`, lanzar error indicando `.env` y ruta esperada. Si TARGET requiere cola/topic y no hay URL/ARN, error claro.
5. Usar **solo valores de config** para `QUEUE_URL` y `TOPIC_ARN` (no override por variables de entorno).
6. Usar publicadores de `common.sqs` y `common.sns`; builder de envelopes desde `<entidad>_builder.py` del mismo directorio.

## 8. README y documentación

- **Al añadir un caso de uso SQS/SNS:** Crear `README.md` dentro de su carpeta con: descripción breve, estructura de archivos, variables de entorno (solo `.env`: `AWS_REGION`, `AWS_ACCOUNT_ID`; nombres en config), cómo ejecutar y, si aplica, modos (archivo, stress test, etc.).
- **Al añadir un database-script:** Crear `README.md` con: descripción, estructura de carpetas, formato de entrada (CSV/JSON), estructura del documento MongoDB, manejo de duplicados/errores, cómo ejecutar, ejemplo de log.
- **README raíz:** Mantener actualizado si se añaden nuevos tipos de carpetas o flujos.
- Formato: títulos claros, listas o tabla para estructura, bloques de código para comandos y ejemplos de `.env`.

## 9. Seguridad

- **Nunca** poner en código: `AWS_ACCOUNT_ID`, `AWS_REGION`, `MONGO_URI`, `MONGO_DATABASE`, credenciales ni URLs con cuenta real. Solo en `.env` (que está en `.gitignore`).
- En `dev/config.py` y `qa/config.py`: leer región y cuenta con `os.getenv(...)`; no usar valores por defecto hardcodeados para cuenta o región.
- En `database-scripts/config.py`: leer `MONGO_URI` y `MONGO_DATABASE` con `os.getenv(...)`.
- No sugerir commitear `.env` ni archivos con credenciales.
- Los `logs/` están en `.gitignore` (`**/logs/`); no subirlos al repo.

## 10. Mensajes de error

- Usar **español** y mensaje claro (qué falta o qué está mal).
- Si fallan variables de entorno: incluir la **ruta esperada** del `.env` (ej. `repo_root / ".env"`) y un ejemplo de línea (ej. `AWS_REGION=us-east-1`).
- Validar pronto (tras cargar config) y fallar con `ValueError` en lugar de seguir con valores vacíos.

## 11. Ejecución

- **Scripts SQS/SNS**: se ejecutan desde la raíz (`python ./ruta/caso/send_message.py`) o desde la carpeta del caso de uso (`python send_message.py`).
- **Scripts database-scripts**: se ejecutan desde la raíz: `python ./database-scripts/<nombre>/run.py`.
- La resolución de la raíz del repo es por `Path(__file__).parent`, no por el directorio de trabajo.
- Si la terminal **no** es interactiva (`sys.stdin.isatty()` es False), no hacer prompts; usar siempre los valores del `config.py` (útil en CI o pipelines).

## 12. Resumen para "añadir algo nuevo"

### Nuevo script SQS/SNS
1. Crear la carpeta del caso de uso con la estructura de la sección 5.
2. Copiar el flujo de un script existente (ej. `bx-cnsr-finmg-billing/proforma-detailed/send_message.py`) y adaptar entidad, builder y rutas.
3. No duplicar lógica de `common/`; usar solo `.env` para datos sensibles; nombres de cola/topic en config como literales.
4. Añadir `README.md` del caso de uso y, si toca, actualizar el README raíz.

### Nuevo script de base de datos
1. Crear la carpeta dentro de `database-scripts/` con la estructura de la sección 5b.
2. Copiar el flujo de un script existente como referencia:
   - **Importar datos a MongoDB:** usar `database-scripts/import-uf-values/` como base.
   - **Consultar MongoDB + llamar API:** usar `database-scripts/notification-resend/` como base.
3. Mantener el patrón: `config.py` → `entities/` → `repositories/` → `services/` → `run.py`.
4. Usar `common/mongo/mongo_client.py` para conexión MongoDB.
5. Implementar DRY_RUN, prompts interactivos, confirmación y logs JSON detallados.
6. Añadir `README.md` con: descripción, estructura, formato de entrada, documento MongoDB, uso.

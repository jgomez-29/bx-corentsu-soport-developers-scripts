# Instrucciones para Copilot – Scripts SQS/SNS

## 1. Resumen del proyecto

- **Qué es:** Repositorio de scripts Python para enviar mensajes a colas SQS y/o topics SNS (AWS).
- **Para quién:** Desarrolladores que necesitan probar o cargar datos contra backends que consumen de SQS/SNS.
- **Características:** Config por ambiente (dev/qa), prompts interactivos al ejecutar (ambiente, destino, cantidad de mensajes), código común en `common/`, sin datos sensibles en el repo (solo en `.env`).

## 2. Stack y dependencias

- **Lenguaje:** Python 3.
- **Dependencias:** `boto3`, `python-dotenv` (ver `requirements.txt`).
- **Entorno:** Variables de entorno desde `.env` en la raíz; fallback de carga manual si `python-dotenv` no está instalado.

## 3. Estándares de código

- Usar **Path** de `pathlib` para rutas; no hardcodear rutas absolutas.
- Imports: estándar primero, luego terceros, luego `common/` (tras añadir repo root a `sys.path`).
- Comentarios y mensajes al usuario en **español**; nombres de variables/funciones en inglés.
- Validar entradas (ambiente, TARGET, cantidad de mensajes) y lanzar `ValueError` con mensaje claro si algo falla.
- No duplicar lógica de SQS/SNS: usar siempre `common.sqs` y `common.sns`.

## 4. Estructura del repo

- **`common/`** – Código compartido (publicadores SQS/SNS, message builder). No tocar sin alinear con todos los casos de uso.
- **Carpetas por caso de uso** (ej. `bx-cnsr-finmg-billing/proforma-detailed/`, `bx-cnsr-finmg-billing-sale-transmission/create-sale-transmission/`, `bx-cnsr-soport-orders-consolidation/`). Cada una debe tener la estructura indicada en la sección 5.

## 5. Estructura obligatoria de un nuevo caso de uso

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

## 6. Reglas de configuración

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

- **Al añadir un caso de uso nuevo:** Crear `README.md` dentro de su carpeta con: descripción breve, estructura de archivos, variables de entorno (solo `.env`: `AWS_REGION`, `AWS_ACCOUNT_ID`; nombres en config), cómo ejecutar y, si aplica, modos (archivo, stress test, etc.).
- **README raíz:** Mantener actualizado si se añaden nuevos tipos de carpetas o flujos; la tabla de “Dentro de cada una” debe seguir reflejando la estructura real.
- Formato: títulos claros, listas o tabla para estructura, bloques de código para comandos y ejemplos de `.env`.

## 9. Seguridad

- **Nunca** poner en código: `AWS_ACCOUNT_ID`, `AWS_REGION`, credenciales AWS ni URLs/ARNs con cuenta real. Solo en `.env` (que está en `.gitignore`).
- En `dev/config.py` y `qa/config.py`: leer región y cuenta con `os.getenv(...)`; no usar valores por defecto hardcodeados para cuenta o región.
- No sugerir commitear `.env` ni archivos con credenciales.

## 10. Mensajes de error

- Usar **español** y mensaje claro (qué falta o qué está mal).
- Si fallan variables de entorno: incluir la **ruta esperada** del `.env` (ej. `repo_root / ".env"`) y un ejemplo de línea (ej. `AWS_REGION=us-east-1`).
- Validar pronto (tras cargar config) y fallar con `ValueError` en lugar de seguir con valores vacíos.

## 11. Ejecución

- Los scripts se pueden ejecutar desde la **raíz del repo** (`python ./ruta/caso/send_message.py`) o desde la **carpeta del caso de uso** (`python send_message.py`). La resolución de la raíz del repo es por `Path(__file__).parent`, no por el directorio de trabajo.
- Si la terminal **no** es interactiva (`sys.stdin.isatty()` es False), no hacer prompts; usar siempre los valores del `config.py` (útil en CI o pipelines).

## 12. Resumen para “añadir algo nuevo”

1. Crear la carpeta del caso de uso con la estructura de la sección 5.
2. Copiar el flujo de un script existente (ej. `bx-cnsr-finmg-billing/proforma-detailed/send_message.py` o `create-sale-transmission/send_message.py`) y adaptar entidad, builder y rutas.
3. No duplicar lógica de `common/`; usar solo `.env` para datos sensibles; nombres de cola/topic en config como literales.
4. Añadir `README.md` del caso de uso y, si toca, actualizar el README raíz.

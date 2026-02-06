# Scripts de Operaciones Backend

Repositorio de scripts Python para operaciones de backend: envío de mensajes a SQS/SNS (AWS) y scripts de base de datos (MongoDB).

- Código compartido en el módulo **`common/`**.
- Sin datos sensibles en el repo (solo en `.env`).

---

## Estructura del repo

### `common/`

Código compartido reutilizable:

| Módulo | Qué hace |
|--------|----------|
| `common/sqs/` | Publicador SQS y message builder |
| `common/sns/` | Publicador SNS |
| `common/mongo/` | Cliente MongoDB reutilizable (`MongoConnection`, context manager) |

### Scripts SQS/SNS (`bx-cnsr-*`)

Cada caso de uso vive en su propia carpeta. Ejemplos:

- `bx-cnsr-finmg-billing/proforma-detailed/`
- `bx-cnsr-finmg-billing-sale-transmission/create-sale-transmission/`
- `bx-cnsr-soport-orders-consolidation/`

Dentro de cada una:

| Archivo o carpeta | Qué es |
|-------------------|--------|
| `config.py` | Config general: ambiente, TARGET, entidad, límites, etc. |
| `dev/config.py` y `qa/config.py` | Config por ambiente. Nombres de cola/topic. URL/ARN se construyen con región y cuenta. |
| `send_message.py` | Script principal: carga config, resuelve raíz del repo, importa `common/`, envía mensajes. |
| `*_builder.py` | Construye payloads y envelopes según el caso de uso. |
| `dev/entities/`, `qa/entities/` | JSON de entrada por ambiente. |

### Scripts de base de datos (`database-scripts/`)

Scripts para operaciones contra MongoDB u otros datastores. Cada sub-carpeta es un script independiente:

| Script | Descripción | Ejecución |
|--------|-------------|-----------|
| `import-uf-values/` | Importa valores UF desde CSVs a MongoDB | `python ./database-scripts/import-uf-values/run.py` |
| `notification-resend/` | Reenvía notificaciones consultando MongoDB + API | `python ./database-scripts/notification-resend/run.py` |

Dentro de cada uno:

| Archivo o carpeta | Qué es |
|-------------------|--------|
| `config.py` | Config general: `MONGO_URI`/`MONGO_DATABASE` de env, DRY_RUN, rutas |
| `run.py` | Script orquestador principal (prompts interactivos, lógica, logs) |
| `entities/` | Estructura del documento MongoDB (tipos, campos, ejemplos) |
| `repositories/` | Acceso a colecciones: constante `COLLECTION_NAME`, funciones de consulta/inserción |
| `services/` | Lógica de negocio: parseo de CSV, clientes HTTP, etc. |
| `reports/` o `*-reports/` | Archivos de entrada (CSV, JSON) |
| `logs/` | Logs JSON de ejecución (generados automáticamente, ignorados por git) |

Cada script tiene su propio `README.md` con detalle completo.

---

## Variables de entorno

En la **raíz del repo** crea un archivo **`.env`** (no se sube a git). Puedes copiar **`.env.example`** y rellenar:

```env
# AWS (scripts SQS/SNS)
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=123456789012

# MongoDB (database-scripts)
MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/
MONGO_DATABASE=nombre-base-datos
```

---

## Cómo ejecutar

### Scripts SQS/SNS

```bash
python ./bx-cnsr-finmg-billing/proforma-detailed/send_message.py
```

### Scripts de base de datos

```bash
python ./database-scripts/import-uf-values/run.py
python ./database-scripts/notification-resend/run.py
```

Los scripts de base de datos tienen prompts interactivos (DRY_RUN, límites, confirmación).

---

## Añadir algo nuevo

Seguir las instrucciones para Copilot en:

- **`.github/copilot-instructions.md`** – Reglas generales del repo (estructura, config, seguridad).
- **`.github/instructions/scripts.instructions.md`** – Reglas al editar scripts SQS/SNS o `common/`.
- **`.github/instructions/database-scripts.instructions.md`** – Reglas al editar database-scripts o `common/mongo/`.
- **`.github/instructions/readme.instructions.md`** – Reglas al editar READMEs.

Así Copilot (u otra IA) genera y mantiene código alineado con los patrones del repo.

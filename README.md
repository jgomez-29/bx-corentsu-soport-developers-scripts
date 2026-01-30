# Scripts de envío a SQS / SNS

Repositorio de scripts Python para enviar mensajes a colas SQS y/o topics SNS (AWS).

- Configuración por ambiente: **dev** y **qa**.
- Código compartido en el módulo **`common/`**.

---

## Estructura del repo

### `common/`

Código compartido: publicadores SQS/SNS y builders de mensajes.

### Carpetas por caso de uso

Cada caso de uso vive en su propia carpeta. Ejemplos:

- `bx-cnsr-finmg-billing/proforma-detailed/`
- `bx-cnsr-finmg-billing-sale-transmission/create-sale-transmission/`
- `bx-cnsr-soport-orders-consolidation/`

Dentro de cada una:

| Archivo o carpeta | Qué es |
|-------------------|--------|
| `config.py` | Config general: ambiente, TARGET, entidad, límites, etc. |
| `dev/config.py` y `qa/config.py` | Config por ambiente. Nombres de cola/topic (no sensibles). URL/ARN se construyen con región y cuenta. |
| `send_to_sqs.py` | Script principal: carga config, resuelve raíz del repo, importa `common/`, envía mensajes. |
| `*_builder.py` | Construye payloads y envelopes según el caso de uso. |
| `dev/entities/`, `qa/entities/` | JSON de entrada por ambiente. |
| `dev/logs/`, `qa/logs/` | Logs de ejecución por ambiente. |

---

## Variables de entorno (solo sensibles)

En la **raíz del repo** crea un archivo **`.env`** (no se sube a git):

```env
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=123456789012
```

- Los **nombres** de cola y topic van en `dev/config.py` y `qa/config.py` (`QUEUE_NAME`, `TOPIC_NAME`). No son sensibles.
- La URL de SQS y el ARN de SNS se construyen en código a partir de región, cuenta y nombre.

---

## Cómo ejecutar un script

1. Clonar el repo y crear `.env` en la raíz con `AWS_REGION` y `AWS_ACCOUNT_ID`.
2. En el `config.py` del caso de uso, elegir `ENVIRONMENT = "dev"` o `"qa"`.
3. Ir a la carpeta del caso de uso y ejecutar:

   ```bash
   python send_to_sqs.py
   ```

Cada caso de uso tiene su propio `README.md` con más detalle (entidades, modos, etc.).

---

## Añadir un nuevo caso de uso

Usar la misma estructura que los existentes y seguir las instrucciones para Copilot en:

- **`.github/copilot-instructions.md`** – Reglas de todo el repo (estructura, config, README).
- **`.github/instructions/scripts.instructions.md`** – Reglas al editar scripts o `common/` (path-specific).

Así Copilot genera y mantiene código alineado con este estándar.

---
applyTo:
  - "README.md"
  - "**/README.md"
---

# Instrucciones al editar README

## Formato general

- Mantener formato claro: títulos con `##`, listas o tabla para estructura, bloques de código (```) para comandos y ejemplos de `.env`.
- Idioma: español para descripciones y títulos.

## README raíz

- Mantener las tablas de estructura alineadas con la organización real del repo.
- Sección de variables de entorno: indicar que en `.env` (raíz) **solo** van datos sensibles.
- Enlazar a `.github/copilot-instructions.md` y a `.github/instructions/` para instrucciones de cómo añadir scripts nuevos.

## README de scripts SQS/SNS

- Incluir: descripción breve, cómo ejecutar (`python send_message.py` o desde raíz con ruta al script), archivos de entidades (`dev/entities/`, `qa/entities/`) y, si aplica, modos (archivo, stress test, etc.).
- Variables de entorno: solo `.env` (`AWS_REGION`, `AWS_ACCOUNT_ID`). Los nombres de cola/topic van en `dev/config.py` y `qa/config.py`.

## README de database-scripts

- Incluir: descripción breve, estructura de carpetas (entities, repositories, services, reports, logs), formato de archivos de entrada (CSV/JSON), estructura del documento MongoDB (colección, campos, tipos, ejemplo), manejo de duplicados/errores, cómo ejecutar (`python ./database-scripts/<nombre>/run.py`), y ejemplo del flujo interactivo (DRY_RUN, confirmación).
- Variables de entorno: solo `.env` (`MONGO_URI`, `MONGO_DATABASE`).
- Documentar los posibles estados del log JSON (INSERTED, ALREADY_EXISTS, SENT, ERROR, DRY_RUN, etc.).

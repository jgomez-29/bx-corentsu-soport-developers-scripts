---
applyTo:
  - "README.md"
  - "**/README.md"
---

# Instrucciones al editar README

- Mantener formato claro: títulos con `##`, listas o tabla para estructura, bloques de código (```) para comandos y ejemplos de `.env`.
- Variables de entorno: indicar que en `.env` (raíz del repo) **solo** van datos sensibles (`AWS_REGION`, `AWS_ACCOUNT_ID`). Los nombres de cola/topic van en `dev/config.py` y `qa/config.py`, no en variables de entorno.
- En README de un caso de uso: incluir descripción breve, cómo ejecutar (`python send_to_sqs.py` o desde raíz con ruta al script), archivos de entidades (`dev/entities/`, `qa/entities/`) y, si aplica, modos (archivo, stress test, etc.).
- En README raíz: mantener la tabla "Dentro de cada una" alineada con la estructura real del repo; enlazar a `.github/copilot-instructions.md` y a `.github/instructions/` para añadir casos de uso.

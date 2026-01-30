---
# Patrones por ESTRUCTURA (no por nombre de carpeta). Así cualquier caso de uso
# futuro que tenga send_message.py, dev/config.py, qa/config.py o *_builder.py
# queda cubierto sin tocar este archivo.
applyTo:
  - "**/send_message.py"
  - "**/dev/config.py"
  - "**/qa/config.py"
  - "**/*_builder.py"
  - "common/**"
---

# Instrucciones al editar scripts o common

- Sigue siempre las reglas de `.github/copilot-instructions.md` (config en dos niveles, .env solo sensibles, nombres en config, resolución de repo root, carga de .env con fallback).
- Al crear o modificar un caso de uso: mantener la estructura `config.py`, `dev/config.py`, `qa/config.py`, `send_message.py`, `*_builder.py`, `dev/entities/`, `qa/entities/`, `README.md`.
- Al tocar `send_message.py`: no quitar prompts interactivos (ambiente, destino, cantidad de mensajes) ni la carga de .env con fallback manual.
- Al tocar `common/`: no romper la interfaz de los publicadores (queue_url/topic_arn, region_name, envelope_builder); no duplicar lógica en los casos de uso. Cualquier cambio debe seguir siendo compatible con todos los `send_message.py` existentes.
- Al editar `dev/config.py` o `qa/config.py`: mantener docstring; `REGION` y `AWS_ACCOUNT_ID` solo con `os.getenv(...)`; `QUEUE_NAME` y `TOPIC_NAME` como literales. No añadir valores por defecto sensibles (cuenta, región).
- Entidades: `dev/entities/` y `qa/entities/` pueden tener archivos JSON distintos por ambiente; las rutas se resuelven según `ENVIRONMENT` y `INPUT_FILE`.
- Al añadir un caso de uso nuevo: crear su `README.md` con variables de entorno (solo .env: AWS_REGION, AWS_ACCOUNT_ID) y cómo ejecutar; actualizar el README raíz si cambia la estructura general. No hace falta añadir rutas nuevas a `applyTo` en este archivo (los globs ya cubren cualquier carpeta con la misma estructura).

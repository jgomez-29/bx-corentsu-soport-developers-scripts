"""
Script para enviar mensajes directamente a SQS (biller-unitary) para pruebas de estrés.

Configuración:
- config.py (raíz): Configuración general (ambiente, cantidad de mensajes, etc.)
- dev/config.py o qa/config.py: Configuración específica del ambiente (queue URL, región)

Destino: solo SQS (queue-finmg-billing-document-request). El consumer biller-unitary
espera el cuerpo como MessageSQS con Message (JSON de DteInformation) y MessageAttributes
(channel, eventType).
"""

import json
import os
import sys
import asyncio
import importlib.util
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any

# Resolver raíz del repo (donde está common/) para imports
current_path = Path(__file__).parent
while current_path != current_path.parent:
    if (current_path / "common").exists():
        repo_root = current_path
        break
    current_path = current_path.parent
else:
    raise RuntimeError("No se encontró el directorio con el módulo 'common/'")

sys.path.insert(0, str(repo_root))

# Cargar .env de la raíz del repo
_env_file = repo_root / ".env"
try:
    from dotenv import load_dotenv
    load_dotenv(str(_env_file))
except ImportError:
    pass
if _env_file.exists() and (not os.getenv("AWS_REGION") or not os.getenv("AWS_ACCOUNT_ID")):
    with open(_env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                key, val = key.strip(), val.strip().strip('"').strip("'")
                if key and val:
                    os.environ[key] = val

from common.sqs.sqs_publisher import SQSPublisher

# ============================================================================
# CARGAR CONFIGURACIÓN (General + Específica del ambiente)
# ============================================================================

script_dir = Path(__file__).parent
general_config_path = script_dir / "config.py"

if not general_config_path.exists():
    raise FileNotFoundError(f"No se encontró config.py general en {script_dir}")

spec_general = importlib.util.spec_from_file_location("config_general", general_config_path)
config_general = importlib.util.module_from_spec(spec_general)
spec_general.loader.exec_module(config_general)

_env_default = config_general.ENVIRONMENT.lower()
_max_default = getattr(config_general, "MAX_MESSAGES", 10)

if sys.stdin.isatty():
    print("\n--- Configuración de ejecución ---")
    _r = input(f"Ambiente (dev/qa) [{_env_default}]: ").strip().lower() or _env_default
    ENVIRONMENT = _r if _r in ("dev", "qa") else _env_default
    while True:
        _r = input(f"Cantidad de mensajes a enviar [{_max_default}]: ").strip()
        if not _r:
            MAX_MESSAGES = _max_default
            break
        try:
            MAX_MESSAGES = int(_r)
            if MAX_MESSAGES > 0:
                break
        except ValueError:
            pass
        print("  Indica un número entero mayor que 0.")
    print()
else:
    ENVIRONMENT = _env_default
    MAX_MESSAGES = _max_default

if ENVIRONMENT not in ["dev", "qa"]:
    raise ValueError(f"Ambiente inválido: {ENVIRONMENT}. Debe ser 'dev' o 'qa'.")

env_config_path = script_dir / ENVIRONMENT / "config.py"
if not env_config_path.exists():
    raise FileNotFoundError(f"No se encontró config.py para el ambiente {ENVIRONMENT} en {env_config_path}")

spec_env = importlib.util.spec_from_file_location("config_env", env_config_path)
config_env = importlib.util.module_from_spec(spec_env)
spec_env.loader.exec_module(config_env)

ENTITY_TYPE = config_general.ENTITY_TYPE
EVENT_TYPE = config_general.EVENT_TYPE
DELAY_MS = config_general.DELAY_MS
LOGS_DIR = config_general.LOGS_DIR
BATCH_SIZE = config_general.BATCH_SIZE
MAX_CONCURRENT = config_general.MAX_CONCURRENT
INPUT_FILE = getattr(config_general, "INPUT_FILE", None)

CONFIG_QUEUE_URL = getattr(config_env, "QUEUE_URL", None)
REGION = getattr(config_env, "REGION", None)
AWS_ACCOUNT_ID = getattr(config_env, "AWS_ACCOUNT_ID", None)

if not REGION or not AWS_ACCOUNT_ID:
    raise ValueError(
        "Define AWS_REGION y AWS_ACCOUNT_ID con valores no vacíos en el archivo .env.\n"
        f"  Ruta esperada: {repo_root / '.env'}\n"
        "  Ejemplo: AWS_REGION=us-east-1  y  AWS_ACCOUNT_ID=123456789012"
    )
if not CONFIG_QUEUE_URL:
    raise ValueError("QUEUE_URL no definido. Revisa que AWS_REGION y AWS_ACCOUNT_ID estén en .env.")

QUEUE_URL = CONFIG_QUEUE_URL

if LOGS_DIR and not Path(LOGS_DIR).is_absolute():
    LOGS_DIR = str(script_dir / LOGS_DIR)

# Resolver ruta de la entidad por ambiente (dev/entities/... o qa/entities/...)
ENTITY_PATH = None
if INPUT_FILE and not Path(INPUT_FILE).is_absolute():
    entity_path = script_dir / ENVIRONMENT / INPUT_FILE
    if entity_path.exists():
        ENTITY_PATH = str(entity_path)

# Importar builder
builder_path = script_dir / "biller_unitary_builder.py"
if not builder_path.exists():
    raise FileNotFoundError(f"No se encontró biller_unitary_builder.py en {script_dir}")
spec_builder = importlib.util.spec_from_file_location("biller_unitary_builder", builder_path)
builder_module = importlib.util.module_from_spec(spec_builder)
spec_builder.loader.exec_module(builder_module)
generate_payloads = builder_module.generate_payloads
load_entity_template = builder_module.load_entity_template
generate_payloads_from_template = builder_module.generate_payloads_from_template
envelope_builder = lambda p: builder_module.envelope_builder(p)

# ============================================================================
# FUNCIÓN PRINCIPAL
# ============================================================================


async def main_async() -> None:
    print_configuration()
    if ENTITY_PATH:
        template = load_entity_template(ENTITY_PATH)
        if template:
            payloads = generate_payloads_from_template(template, MAX_MESSAGES)
            print(f"Usando plantilla del ambiente: {ENVIRONMENT}/{INPUT_FILE}")
        else:
            payloads = generate_payloads(MAX_MESSAGES)
            print("Generando mensajes sintéticos (plantilla no encontrada).")
    else:
        payloads = generate_payloads(MAX_MESSAGES)
        print("Generando mensajes sintéticos (sin archivo de plantilla).")
    print(f"  {len(payloads)} mensajes generados.\n")

    if payloads:
        p0 = payloads[0]
        env0 = envelope_builder(p0)
        print("=== VERIFICACIÓN DEL ENVELOPE (primer mensaje) ===")
        print(f"  identifier: {p0.get('identifier')}")
        print(f"  Message es string: {isinstance(env0.get('Message'), str)}")
        print(f"  MessageAttributes.channel: {env0.get('MessageAttributes', {}).get('channel', {}).get('Value')}")
        print(f"  MessageAttributes.eventType: {env0.get('MessageAttributes', {}).get('eventType', {}).get('Value')}")
        print("===============================\n")

    publisher = SQSPublisher(
        queue_url=QUEUE_URL,
        region_name=REGION,
        max_concurrent=MAX_CONCURRENT,
        envelope_builder=envelope_builder,
    )

    print(f"Enviando {len(payloads)} mensajes a la cola SQS...")
    if len(payloads) > BATCH_SIZE:
        ok_count, error_count = await send_in_batches(publisher, payloads, BATCH_SIZE, verbose=(len(payloads) <= 50))
    else:
        ok_count, error_count = await send_one_by_one(
            publisher, payloads, DELAY_MS, verbose=(len(payloads) <= 10)
        )

    identifiers_sent = [p.get("identifier", "") for p in payloads]
    log_file = save_log(identifiers_sent, ok_count, error_count)

    print("\n" + "=" * 50)
    print("=== RESUMEN FINAL ===")
    print(f"Total: {len(payloads)}")
    print(f"Exitosos: {ok_count}")
    print(f"Fallidos: {error_count}")
    if log_file:
        print(f"Log guardado en: {log_file}")
    print("=" * 50)


def main() -> None:
    asyncio.run(main_async())


# ============================================================================
# FUNCIONES DE UTILIDAD
# ============================================================================


def print_configuration() -> None:
    print("=" * 60)
    print("=== CONFIGURACIÓN (biller-unitary SQS) ===")
    print("=" * 60)
    print(f"   • Ambiente: {ENVIRONMENT}")
    print(f"   • Máximo de mensajes: {MAX_MESSAGES}")
    print("   • Destino: SQS")
    print(f"   • Entidad (plantilla): {f'{ENVIRONMENT}/{INPUT_FILE}' if INPUT_FILE else 'ninguna (sintéticos)'}")
    if ENTITY_PATH:
        print(f"   • Ruta plantilla: {ENTITY_PATH}")
    print(f"   • Tipo entidad: {ENTITY_TYPE}")
    print(f"   • Tipo evento: {EVENT_TYPE}")
    print(f"   • Cola SQS: {QUEUE_URL}")
    print(f"   • Región: {REGION}")
    print(f"   • Delay: {DELAY_MS}ms | Lote: {BATCH_SIZE} | Concurrencia: {MAX_CONCURRENT}")
    print(f"   • Logs: {LOGS_DIR}/")
    print("=" * 60)
    print()


async def send_in_batches(
    publisher: SQSPublisher,
    items: List[Dict[str, Any]],
    batch_size: int,
    verbose: bool = False,
) -> tuple:
    ok_count = error_count = 0
    total = len(items)
    batches = [items[i : i + batch_size] for i in range(0, total, batch_size)]
    total_batches = len(batches)
    print(f"Dividido en {total_batches} lote(s) de hasta {batch_size} mensajes\n")

    for batch_idx, batch in enumerate(batches, 1):
        results = await publisher.publish_batch(batch)
        for item, result in zip(batch, results):
            if result.get("status") == "OK":
                ok_count += 1
            else:
                error_count += 1
                if verbose or error_count <= 5:
                    print(f"  ERROR - {item.get('identifier', '')}: {result.get('error')}")
        if batch_idx <= 3 or batch_idx % 10 == 0 or batch_idx == total_batches:
            batch_end = min(batch_idx * batch_size, total)
            print(f"[Lote {batch_idx}/{total_batches}] Total: {batch_end}/{total} | OK: {ok_count} | ERROR: {error_count}")
    return ok_count, error_count


async def send_one_by_one(
    publisher: SQSPublisher,
    items: List[Dict[str, Any]],
    delay_ms: int = 0,
    verbose: bool = False,
) -> tuple:
    ok_count = error_count = 0
    total = len(items)
    for idx, item in enumerate(items, 1):
        results = await publisher.publish_batch([item])
        result = results[0] if results else {}
        if result.get("status") == "OK":
            ok_count += 1
            if verbose:
                print(f"  [{idx}/{total}] OK - identifier: {item.get('identifier', '')[:40]}...")
        else:
            error_count += 1
            print(f"  [{idx}/{total}] ERROR - {item.get('identifier', '')}: {result.get('error')}")
        if delay_ms > 0 and idx < total:
            await asyncio.sleep(delay_ms / 1000.0)
    return ok_count, error_count


def save_log(identifiers: List[str], ok_count: int, error_count: int) -> str:
    """Guarda un log JSON con los identifiers enviados y resumen."""
    if not LOGS_DIR:
        return ""
    Path(LOGS_DIR).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = str(Path(LOGS_DIR) / f"biller_unitary_{timestamp}.json")
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "environment": ENVIRONMENT,
                "queue_url": QUEUE_URL,
                "total": len(identifiers),
                "ok_count": ok_count,
                "error_count": error_count,
                "identifiers": identifiers,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
    return log_file


if __name__ == "__main__":
    main()

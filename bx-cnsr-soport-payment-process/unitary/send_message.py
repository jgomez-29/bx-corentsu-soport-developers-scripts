"""
Script para enviar mensajes unitarios a SNS (payment process, eventType paymentProcessUnitary).

Configuración: config.py (general), dev/config.py o qa/config.py (ambiente).
Destino: SNS topic (topic-finmg-payment-process-fragment).
"""

import json
import os
import sys
import asyncio
import importlib.util
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Callable

# Resolver raíz del repo (donde está common/)
current_path = Path(__file__).parent
while current_path != current_path.parent:
    if (current_path / "common").exists():
        repo_root = current_path
        break
    current_path = current_path.parent
else:
    raise RuntimeError("No se encontró el directorio con el módulo 'common/'")

sys.path.insert(0, str(repo_root))

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

from common.sns.sns_publisher import SNSPublisher

# ============================================================================
# CARGAR CONFIGURACIÓN
# ============================================================================

script_dir = Path(__file__).parent
general_config_path = script_dir / "config.py"
if not general_config_path.exists():
    raise FileNotFoundError(f"No se encontró config.py general en {script_dir}")

spec_general = importlib.util.spec_from_file_location("config_general", general_config_path)
config_general = importlib.util.module_from_spec(spec_general)
spec_general.loader.exec_module(config_general)

_env_default = config_general.ENVIRONMENT.lower()
_target_default = (getattr(config_general, "TARGET", "sns") or "sns").lower()
_max_default = getattr(config_general, "MAX_MESSAGES", 10)

if sys.stdin.isatty():
    print("\n--- Configuración de ejecución ---")
    _r = input(f"Ambiente (dev/qa) [{_env_default}]: ").strip().lower() or _env_default
    ENVIRONMENT = _r if _r in ("dev", "qa") else _env_default
    _r = input(f"Destino (sqs/sns/both) [{_target_default}]: ").strip().lower() or _target_default
    TARGET = _r if _r in ("sqs", "sns", "both") else _target_default
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
    TARGET = _target_default
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

CONFIG_TOPIC_ARN = getattr(config_env, "TOPIC_ARN", None)
REGION = getattr(config_env, "REGION", None)
AWS_ACCOUNT_ID = getattr(config_env, "AWS_ACCOUNT_ID", None)

if not REGION or not AWS_ACCOUNT_ID:
    raise ValueError(
        "Define AWS_REGION y AWS_ACCOUNT_ID con valores no vacíos en el archivo .env.\n"
        f"  Ruta esperada: {repo_root / '.env'}\n"
        "  Ejemplo: AWS_REGION=us-east-1  y  AWS_ACCOUNT_ID=123456789012"
    )
if TARGET in ("sns", "both") and not CONFIG_TOPIC_ARN:
    raise ValueError(f"Cuando TARGET es '{TARGET}' debes definir TOPIC_NAME en {ENVIRONMENT}/config.py.")

TOPIC_ARN = CONFIG_TOPIC_ARN
if LOGS_DIR and not Path(LOGS_DIR).is_absolute():
    LOGS_DIR = str(script_dir / ENVIRONMENT / LOGS_DIR)

builder_path = script_dir / "payment_process_unitary_builder.py"
if not builder_path.exists():
    raise FileNotFoundError(f"No se encontró payment_process_unitary_builder.py en {script_dir}")
spec_builder = importlib.util.spec_from_file_location("payment_process_unitary_builder", builder_path)
builder_module = importlib.util.module_from_spec(spec_builder)
spec_builder.loader.exec_module(builder_module)
generate_payloads = builder_module.generate_payloads
envelope_builder = builder_module.envelope_builder

# ============================================================================
# MAIN
# ============================================================================

async def main_async() -> None:
    print_configuration()
    print("Generando mensajes unitarios (paymentProcessUnitary)...")
    payloads = generate_payloads(MAX_MESSAGES)
    print(f"{len(payloads)} mensajes generados.\n")

    if payloads:
        p0 = payloads[0]
        env0 = envelope_builder(p0)
        print("=== VERIFICACIÓN DEL ENVELOPE (primer mensaje) ===")
        print(f"requestId: {p0.get('requestId')}")
        print(f"eventType: paymentProcessUnitary")
        print(f"Message es string: {isinstance(env0.get('Message'), str)}")
        print("===============================\n")

    publisher = SNSPublisher(
        topic_arn=TOPIC_ARN,
        region_name=REGION,
        max_concurrent=MAX_CONCURRENT,
        envelope_builder=envelope_builder,
    )

    print(f"📤 Enviando {len(payloads)} mensajes al topic SNS...")
    if len(payloads) > BATCH_SIZE:
        ok_count, error_count = await send_in_batches(publisher, payloads, BATCH_SIZE, len(payloads) <= 50)
    else:
        ok_count, error_count = await send_one_by_one(publisher, payloads, envelope_builder, DELAY_MS, len(payloads) <= 10)

    print("\n" + "=" * 50)
    print("=== RESUMEN FINAL ===")
    print(f"Total: {len(payloads)}")
    print(f"Exitosos: {ok_count}")
    print(f"Fallidos: {error_count}")
    print("=" * 50)


def print_configuration():
    print("=" * 60)
    print("=== CONFIGURACIÓN (payment-process-unitary) ===")
    print("=" * 60)
    print(f"   • Ambiente: {ENVIRONMENT}")
    print(f"   • Máximo de mensajes: {MAX_MESSAGES}")
    print("🌐 Destino:")
    print(f"   • TARGET: {TARGET}")
    print(f"   • Tipo entidad: {ENTITY_TYPE}")
    print(f"   • Tipo evento: {EVENT_TYPE}")
    print(f"   • Topic SNS: {TOPIC_ARN}")
    print(f"   • Región: {REGION}")
    print(f"   • Delay: {DELAY_MS}ms | Lote: {BATCH_SIZE} | Concurrencia: {MAX_CONCURRENT}")
    print("=" * 60)
    print()


async def send_in_batches(publisher, items: List[Dict], batch_size: int, verbose: bool) -> tuple:
    ok_count = error_count = 0
    total = len(items)
    batches = [items[i:i + batch_size] for i in range(0, total, batch_size)]
    for batch_idx, batch in enumerate(batches, 1):
        results = await publisher.publish_batch(batch)
        for r in results:
            if r.get("status") == "OK":
                ok_count += 1
            else:
                error_count += 1
                if verbose or error_count <= 5:
                    print(f"✗ ERROR: {r.get('error')}")
        if batch_idx <= 3 or batch_idx % 10 == 0 or batch_idx == len(batches):
            print(f"[Lote {batch_idx}/{len(batches)}] OK: {ok_count} | ERROR: {error_count}")
    return ok_count, error_count


async def send_one_by_one(publisher, items: List[Dict], envelope_builder_fn: Callable, delay_ms: int, verbose: bool) -> tuple:
    ok_count = error_count = 0
    total = len(items)
    for idx, item in enumerate(items, 1):
        results = await publisher.publish_batch([item])
        result = results[0] if results else {}
        if result.get("status") == "OK":
            ok_count += 1
            if verbose:
                print(f"[{idx}/{total}] ✓ OK - requestId: {item.get('requestId', '')[:20]}...")
        else:
            error_count += 1
            print(f"[{idx}/{total}] ✗ ERROR: {result.get('error')}")
        if delay_ms and idx < total:
            await asyncio.sleep(delay_ms / 1000.0)
    return ok_count, error_count


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()

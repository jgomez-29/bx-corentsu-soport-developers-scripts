"""
Script para enviar mensajes a SQS para proformas (proforma-detailed).

Configuración:
- config.py (raíz): Configuración general (ambiente, cantidad de mensajes, etc.)
- dev/config.py o qa/config.py: Configuración específica del ambiente (queue URL, región)
"""

import json
import os
import sys
import asyncio
import importlib.util
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Callable

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
# Fallback: si las variables siguen vacías (dotenv no instalado o path), cargar .env manualmente
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
from common.sqs.message_builder import MessageBuilder
from common.sns.sns_publisher import SNSPublisher, DualPublisher

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

# Prompts interactivos (si la terminal es interactiva)
_env_default = config_general.ENVIRONMENT.lower()
_target_default = (getattr(config_general, "TARGET", "sqs") or "sqs").lower()
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
    raise ValueError(f"Ambiente inválido: {ENVIRONMENT}. Debe ser 'dev' o 'qa' en config.py")

env_config_path = script_dir / ENVIRONMENT / "config.py"
if not env_config_path.exists():
    raise FileNotFoundError(f"No se encontró config.py para el ambiente {ENVIRONMENT} en {env_config_path}")

spec_env = importlib.util.spec_from_file_location("config_env", env_config_path)
config_env = importlib.util.module_from_spec(spec_env)
spec_env.loader.exec_module(config_env)

# Variables de la configuración general (ENVIRONMENT, TARGET, MAX_MESSAGES ya vienen del prompt o del config)
ENTITY_TYPE = config_general.ENTITY_TYPE
EVENT_TYPE = config_general.EVENT_TYPE
DELAY_MS = config_general.DELAY_MS
LOGS_DIR = config_general.LOGS_DIR
INPUT_FILE = config_general.INPUT_FILE
PROFORMA_SERIES_LIST = config_general.PROFORMA_SERIES_LIST
ACCOUNT = config_general.ACCOUNT
BATCH_SIZE = config_general.BATCH_SIZE
MAX_CONCURRENT = config_general.MAX_CONCURRENT

if TARGET not in ("sqs", "sns", "both"):
    raise ValueError(f"TARGET debe ser 'sqs', 'sns' o 'both'. Recibido: {TARGET}")

CONFIG_QUEUE_URL = getattr(config_env, "QUEUE_URL", None)
CONFIG_TOPIC_ARN = getattr(config_env, "TOPIC_ARN", None)
REGION = getattr(config_env, "REGION", None)
AWS_ACCOUNT_ID = getattr(config_env, "AWS_ACCOUNT_ID", None)

if not REGION or not AWS_ACCOUNT_ID:
    _env_path = repo_root / ".env"
    raise ValueError(
        "Define AWS_REGION y AWS_ACCOUNT_ID con valores no vacíos en el archivo .env.\n"
        f"  Ruta esperada: {_env_path}\n"
        "  Ejemplo: AWS_REGION=us-east-1  y  AWS_ACCOUNT_ID=123456789012"
    )
if TARGET in ("sqs", "both") and not CONFIG_QUEUE_URL:
    raise ValueError(f"Cuando TARGET es '{TARGET}' se necesita QUEUE_URL. Revisa que AWS_REGION y AWS_ACCOUNT_ID estén en .env")
if TARGET in ("sns", "both") and not CONFIG_TOPIC_ARN:
    raise ValueError(f"Cuando TARGET es '{TARGET}' debes definir TOPIC_NAME en {ENVIRONMENT}/config.py para construir TOPIC_ARN")

# Resolver INPUT_FILE al folder del ambiente
if INPUT_FILE and not Path(INPUT_FILE).is_absolute():
    env_input = script_dir / ENVIRONMENT / INPUT_FILE
    INPUT_FILE = str(env_input) if env_input.exists() else str(script_dir / INPUT_FILE)

# LOGS_DIR relativo al ambiente
if LOGS_DIR and not Path(LOGS_DIR).is_absolute():
    LOGS_DIR = str(script_dir / ENVIRONMENT / LOGS_DIR)

# Importar proforma_builder
builder_path = script_dir / "proforma_builder.py"
if not builder_path.exists():
    raise FileNotFoundError(f"No se encontró proforma_builder.py en {script_dir}")
spec_builder = importlib.util.spec_from_file_location("proforma_builder", builder_path)
proforma_builder = importlib.util.module_from_spec(spec_builder)
spec_builder.loader.exec_module(proforma_builder)
load_proformas = proforma_builder.load_proformas

# ============================================================================
# CONFIGURACIÓN (URL/ARN se construyen en config desde REGION + ACCOUNT_ID + nombres)
# ============================================================================

QUEUE_URL = CONFIG_QUEUE_URL
TOPIC_ARN = CONFIG_TOPIC_ARN


# ============================================================================
# FUNCIÓN PRINCIPAL
# ============================================================================

async def main_async() -> None:
    print_configuration()
    envelope_builder = get_envelope_builder()

    print("Cargando proformas desde archivo/lista...")
    items = load_proformas(INPUT_FILE, PROFORMA_SERIES_LIST, ACCOUNT)

    if not INPUT_FILE and not PROFORMA_SERIES_LIST:
        raise ValueError(
            "Debes especificar INPUT_FILE o PROFORMA_SERIES_LIST. "
            "IMPORTANTE: Los proformaSeries deben existir en la base de datos."
        )

    if not items:
        print("No hay proformas para procesar. Abortando.")
        return

    total_loaded = len(items)
    if MAX_MESSAGES and MAX_MESSAGES > 0:
        if total_loaded >= MAX_MESSAGES:
            items = items[:MAX_MESSAGES]
            print(f"{total_loaded} proformas cargadas, limitando a {MAX_MESSAGES} mensajes\n")
        else:
            repetitions_needed = (MAX_MESSAGES // total_loaded) + (1 if MAX_MESSAGES % total_loaded > 0 else 0)
            items = (items * repetitions_needed)[:MAX_MESSAGES]
            print(f"{total_loaded} proforma(s) cargada(s), repitiendo hasta {MAX_MESSAGES} mensajes\n")
    else:
        print(f"{len(items)} proformas cargadas\n")

    if items:
        proforma = items[0]
        envelope = envelope_builder(proforma)
        print("\n=== VERIFICACIÓN DEL ENVELOPE (primer mensaje) ===")
        print(f"ProformaSerie: {proforma.get('proformaSerie')}")
        print(f"Account: {proforma.get('account', 'No especificado (se obtendrá de la BD)')}")
        print(f"Message es string: {isinstance(envelope.get('Message'), str)}")
        print(f"MessageAttributes.eventType.Value: {envelope.get('MessageAttributes', {}).get('eventType', {}).get('Value')}")
        print("===============================\n")

    # Crear publisher según TARGET (sqs, sns o both)
    if TARGET == "sqs":
        publisher = SQSPublisher(
            queue_url=QUEUE_URL,
            region_name=REGION,
            max_concurrent=MAX_CONCURRENT,
            envelope_builder=envelope_builder,
        )
    elif TARGET == "sns":
        publisher = SNSPublisher(
            topic_arn=TOPIC_ARN,
            region_name=REGION,
            max_concurrent=MAX_CONCURRENT,
            envelope_builder=envelope_builder,
        )
    else:
        publisher = DualPublisher(
            SQSPublisher(queue_url=QUEUE_URL, region_name=REGION, max_concurrent=MAX_CONCURRENT, envelope_builder=envelope_builder),
            SNSPublisher(topic_arn=TOPIC_ARN, region_name=REGION, max_concurrent=MAX_CONCURRENT, envelope_builder=envelope_builder),
        )

    dest_label = "queue" if TARGET == "sqs" else "topic" if TARGET == "sns" else "queue y topic"
    print(f"📤 Enviando {len(items)} mensajes a la {dest_label}...")
    if len(items) > BATCH_SIZE:
        ok_count, error_count, proforma_series_sent = await send_in_batches(
            publisher, items, BATCH_SIZE, verbose=(len(items) <= 50)
        )
    else:
        ok_count, error_count, proforma_series_sent = await send_one_by_one(
            publisher, items, envelope_builder, DELAY_MS, verbose=(len(items) <= 10)
        )

    log_file = save_proforma_series_log(proforma_series_sent)

    print("\n" + "=" * 50)
    print("=== RESUMEN FINAL ===")
    print(f"Total: {len(items)}")
    print(f"Exitosos: {ok_count}")
    print(f"Fallidos: {error_count}")
    print(f"ProformaSeries procesadas guardadas en: {log_file}")
    print("=" * 50)


def main() -> None:
    asyncio.run(main_async())


# ============================================================================
# FUNCIONES DE UTILIDAD
# ============================================================================

def print_configuration():
    print("=" * 60)
    print("=== CONFIGURACIÓN ===")
    print("=" * 60)
    print(f"   • Ambiente: {ENVIRONMENT}")
    if PROFORMA_SERIES_LIST:
        print(f"   • ProformaSeries desde lista: {len(PROFORMA_SERIES_LIST)}")
    elif INPUT_FILE:
        print(f"   • Archivo: {INPUT_FILE}")
    print(f"   • Account: {ACCOUNT if ACCOUNT else 'No especificado (se obtendrá de la BD)'}")
    if MAX_MESSAGES and MAX_MESSAGES > 0:
        print(f"   • Máximo de mensajes: {MAX_MESSAGES}")
    print()
    print("🌐 Destino:")
    print(f"   • TARGET: {TARGET}")
    print(f"   • Tipo entidad: {ENTITY_TYPE}")
    print(f"   • Tipo evento: {EVENT_TYPE}")
    if TARGET in ("sqs", "both"):
        print(f"   • Cola SQS: {QUEUE_URL}")
    if TARGET in ("sns", "both"):
        print(f"   • Topic SNS: {TOPIC_ARN}")
    print(f"   • Región: {REGION}")
    print(f"   • Delay: {DELAY_MS}ms | Lote: {BATCH_SIZE} | Concurrencia: {MAX_CONCURRENT}")
    print(f"📝 Logs: {LOGS_DIR}/")
    print("=" * 60)
    print()


def get_envelope_builder() -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    return MessageBuilder.build_proforma


async def send_in_batches(
    publisher,
    items: List[Dict[str, Any]],
    batch_size: int,
    verbose: bool = False,
) -> tuple[int, int, List[str]]:
    total = len(items)
    ok_count = error_count = 0
    proforma_series_sent = []
    batches = [items[i:i + batch_size] for i in range(0, total, batch_size)]
    total_batches = len(batches)
    print(f"📦 Dividido en {total_batches} lote(s) de hasta {batch_size} mensajes\n")

    for batch_idx, batch in enumerate(batches, 1):
        batch_start = (batch_idx - 1) * batch_size + 1
        batch_end = min(batch_start + len(batch) - 1, total)
        results = await publisher.publish_batch(batch)
        for item, result in zip(batch, results):
            proforma_series_sent.append(item.get("proformaSerie", "UNKNOWN"))
            if result.get("status") == "OK":
                ok_count += 1
            else:
                error_count += 1
                if verbose or error_count <= 5:
                    print(f"✗ ERROR - {item.get('proformaSerie')}: {result.get('error')}")
        if batch_idx <= 3 or batch_idx % 10 == 0 or batch_idx == total_batches:
            print(f"[Lote {batch_idx}/{total_batches}] ✓ {len(batch)} mensajes (Total: {batch_end}/{total}, OK: {ok_count}, ERROR: {error_count})")
    return ok_count, error_count, proforma_series_sent


async def send_one_by_one(
    publisher,
    items: List[Dict[str, Any]],
    envelope_builder: Callable[[Dict[str, Any]], Dict[str, Any]],
    delay_ms: int = 0,
    verbose: bool = False,
) -> tuple[int, int, List[str]]:
    total = len(items)
    ok_count = error_count = 0
    proforma_series_sent = []
    for idx, item in enumerate(items, 1):
        proforma_serie = item.get("proformaSerie", "UNKNOWN")
        proforma_series_sent.append(proforma_serie)
        if verbose and idx <= 3:
            envelope = envelope_builder(item)
            print(f"\n[{idx}/{total}] eventType: {envelope.get('MessageAttributes', {}).get('eventType', {}).get('Value')}")
        result = await publisher.publish_batch([item])
        status = result[0].get("status")
        if status == "OK":
            ok_count += 1
        else:
            error_count += 1
            print(f"[{idx}/{total}] ✗ ERROR - {proforma_serie}: {result[0].get('error')}")
        if delay_ms > 0 and idx < total:
            await asyncio.sleep(delay_ms / 1000.0)
    return ok_count, error_count, proforma_series_sent


def generate_log_filename() -> str:
    Path(LOGS_DIR).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return str(Path(LOGS_DIR) / f"proforma_series_{timestamp}.json")


def save_proforma_series_log(proforma_series: List[str]) -> str:
    log_file = generate_log_filename()
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump({
            "total": len(proforma_series),
            "proformaSeries": proforma_series,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }, f, indent=2, ensure_ascii=False)
    print(f"✓ ProformaSeries guardadas en: {log_file}")
    return log_file


if __name__ == "__main__":
    main()

"""
Script para enviar mensajes a SQS para SaleTransmission (CreateSaleTransmissionUseCase).

Configuración:
- config.py (raíz): Configuración general (ambiente, cantidad de mensajes, etc.)
- dev/config.py o qa/config.py: Configuración específica del ambiente (queue URL, región)
"""

import json
import os
import sys
import asyncio
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

import importlib.util

# 1. Cargar configuración GENERAL (desde la raíz)
script_dir = Path(__file__).parent
general_config_path = script_dir / "config.py"

if not general_config_path.exists():
    raise FileNotFoundError(
        f"No se encontró config.py general en {script_dir}. "
        "Debe existir un config.py en la raíz de create-sale-transmission/"
    )

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
    raise ValueError(
        f"Ambiente inválido: {ENVIRONMENT}. "
        "Debe ser 'dev' o 'qa' en config.py (configuración general)"
    )

# 2. Cargar configuración ESPECÍFICA del ambiente (dev/config.py o qa/config.py)
env_config_path = script_dir / ENVIRONMENT / "config.py"

if not env_config_path.exists():
    raise FileNotFoundError(
        f"No se encontró config.py para el ambiente {ENVIRONMENT} en {env_config_path}. "
        f"Debe existir {ENVIRONMENT}/config.py con la configuración específica del ambiente."
    )

spec_env = importlib.util.spec_from_file_location("config_env", env_config_path)
config_env = importlib.util.module_from_spec(spec_env)
spec_env.loader.exec_module(config_env)

# 3. Combinar configuraciones (ENVIRONMENT, TARGET, MAX_MESSAGES ya vienen del prompt o del config)
# Variables de la configuración general
ENTITY_TYPE = config_general.ENTITY_TYPE
EVENT_TYPE = config_general.EVENT_TYPE
DELAY_MS = config_general.DELAY_MS
LOGS_DIR = config_general.LOGS_DIR
INPUT_FILE = config_general.INPUT_FILE
SALE_TRANSMISSIONS_LIST = config_general.SALE_TRANSMISSIONS_LIST
BATCH_SIZE = config_general.BATCH_SIZE
MAX_CONCURRENT = config_general.MAX_CONCURRENT
STRESS_TEST_ENABLED = config_general.STRESS_TEST_ENABLED
STRESS_TEST_BASE_SII_FOLIO = config_general.STRESS_TEST_BASE_SII_FOLIO
STRESS_TEST_START = config_general.STRESS_TEST_START
STRESS_TEST_TEMPLATE_FILE = config_general.STRESS_TEST_TEMPLATE_FILE

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

# Ajustar rutas relativas al ambiente si es necesario
if INPUT_FILE and not Path(INPUT_FILE).is_absolute():
    env_input_file = script_dir / ENVIRONMENT / INPUT_FILE
    if env_input_file.exists():
        INPUT_FILE = str(env_input_file)
    else:
        root_input_file = script_dir / INPUT_FILE
        if root_input_file.exists():
            INPUT_FILE = str(root_input_file)

if STRESS_TEST_TEMPLATE_FILE and not Path(STRESS_TEST_TEMPLATE_FILE).is_absolute():
    env_template_file = script_dir / ENVIRONMENT / STRESS_TEST_TEMPLATE_FILE
    if env_template_file.exists():
        STRESS_TEST_TEMPLATE_FILE = str(env_template_file)
    else:
        root_template_file = script_dir / STRESS_TEST_TEMPLATE_FILE
        if root_template_file.exists():
            STRESS_TEST_TEMPLATE_FILE = str(root_template_file)

if LOGS_DIR and not Path(LOGS_DIR).is_absolute():
    LOGS_DIR = str(script_dir / ENVIRONMENT / LOGS_DIR)

# Importar sale_transmission_builder desde el directorio del script
script_dir = Path(__file__).parent
builder_path = script_dir / "sale_transmission_builder.py"
if not builder_path.exists():
    raise FileNotFoundError(f"No se encontró sale_transmission_builder.py en {script_dir}")

spec_builder = importlib.util.spec_from_file_location("sale_transmission_builder", builder_path)
sale_transmission_builder = importlib.util.module_from_spec(spec_builder)
spec_builder.loader.exec_module(sale_transmission_builder)
load_sale_transmissions = sale_transmission_builder.load_sale_transmissions
generate_sale_transmissions_for_stress_test = sale_transmission_builder.generate_sale_transmissions_for_stress_test

# ============================================================================
# CONFIGURACIÓN (URL/ARN se construyen en config desde REGION + ACCOUNT_ID + nombres)
# ============================================================================

QUEUE_URL = CONFIG_QUEUE_URL
TOPIC_ARN = CONFIG_TOPIC_ARN


# ============================================================================
# FUNCIÓN PRINCIPAL
# ============================================================================

async def main_async() -> None:
    """Función principal - aquí está el flujo completo del script"""
    print_configuration()
    envelope_builder = get_envelope_builder()

    if STRESS_TEST_ENABLED:
        print(f"Generando {MAX_MESSAGES} SaleTransmission para pruebas de estrés...")
        if not STRESS_TEST_TEMPLATE_FILE:
            raise ValueError("STRESS_TEST_TEMPLATE_FILE es requerido cuando STRESS_TEST_ENABLED=True")
        template_path = Path.cwd() / STRESS_TEST_TEMPLATE_FILE
        with open(template_path, "r", encoding="utf-8") as f:
            template_data = json.load(f)
        if isinstance(template_data, list):
            if len(template_data) == 0:
                raise ValueError("El template no puede estar vacío")
            template = template_data[0]
        else:
            template = template_data
        items = generate_sale_transmissions_for_stress_test(
            STRESS_TEST_BASE_SII_FOLIO,
            STRESS_TEST_START,
            MAX_MESSAGES,
            template
        )
        print(f"{len(items)} SaleTransmission generados\n")
    else:
        print("Cargando SaleTransmission desde archivo/lista...")
        items = load_sale_transmissions(INPUT_FILE, SALE_TRANSMISSIONS_LIST)
        if not INPUT_FILE and not SALE_TRANSMISSIONS_LIST:
            raise ValueError(
                "Debes especificar una de las siguientes opciones:\n"
                "  - INPUT_FILE: Ruta a archivo JSON con SaleTransmission\n"
                "  - SALE_TRANSMISSIONS_LIST: Lista directa de SaleTransmission\n"
                "  - STRESS_TEST_ENABLED=True: Para generar mensajes automáticamente"
            )
        if not items:
            print("No hay SaleTransmission para procesar. Abortando.")
            return
        total_loaded = len(items)
        if MAX_MESSAGES and MAX_MESSAGES > 0:
            if total_loaded >= MAX_MESSAGES:
                items = items[:MAX_MESSAGES]
                print(f"{total_loaded} SaleTransmission cargados, limitando a {MAX_MESSAGES} mensajes\n")
            else:
                repetitions_needed = (MAX_MESSAGES // total_loaded) + (1 if MAX_MESSAGES % total_loaded > 0 else 0)
                items = (items * repetitions_needed)[:MAX_MESSAGES]
                print(f"{total_loaded} SaleTransmission cargado(s), repitiendo hasta {MAX_MESSAGES} mensajes\n")
        else:
            print(f"{len(items)} SaleTransmission cargados\n")

    if items:
        sale_transmission = items[0]
        envelope = envelope_builder(sale_transmission)
        print("\n=== VERIFICACIÓN DEL ENVELOPE (primer mensaje) ===")
        print(f"SiiFolio: {sale_transmission.get('siiFolio')}")
        print(f"Type: {sale_transmission.get('type')}")
        print(f"Account: {sale_transmission.get('account')}")
        print(f"Message es string: {isinstance(envelope.get('Message'), str)}")
        print(
            f"MessageAttributes.eventType.Value: {envelope.get('MessageAttributes', {}).get('eventType', {}).get('Value')}"
        )
        print("===============================\n")

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
    print(f"   • Tamaño de lote: {BATCH_SIZE}")
    print(f"   • Concurrencia máxima: {MAX_CONCURRENT}\n")

    if len(items) > BATCH_SIZE:
        ok_count, error_count, sii_folios_sent = await send_in_batches(
            publisher, items, BATCH_SIZE, verbose=(len(items) <= 50)
        )
    else:
        ok_count, error_count, sii_folios_sent = await send_one_by_one(
            publisher, items, envelope_builder, DELAY_MS, verbose=(len(items) <= 10)
        )

    log_file = save_sii_folios_log(sii_folios_sent)
    print("\n" + "=" * 50)
    print("=== RESUMEN FINAL ===")
    print(f"Total: {len(items)}")
    print(f"Exitosos: {ok_count}")
    print(f"Fallidos: {error_count}")
    print(f"SiiFolios procesados guardados en: {log_file}")
    print("=" * 50)


def main() -> None:
    """Punto de entrada principal"""
    asyncio.run(main_async())


# ============================================================================
# FUNCIONES DE UTILIDAD
# ============================================================================

def print_configuration():
    """Imprime la configuración actual del script"""
    print("=" * 60)
    print("=== CONFIGURACIÓN ===")
    print("=" * 60)
    print(f"🌍 Ambiente: {ENVIRONMENT.upper()} (definido en config.py general)")
    print(f"📁 Config específica: {ENVIRONMENT}/config.py")
    print()
    if STRESS_TEST_ENABLED:
        print("🔧 Modo: PRUEBAS DE ESTRÉS")
        print(f"   • Base SiiFolio: {STRESS_TEST_BASE_SII_FOLIO}")
        print(f"   • Start: {STRESS_TEST_START}")
        print(f"   • Total mensajes: {MAX_MESSAGES}")
        print(f"   • Template: {STRESS_TEST_TEMPLATE_FILE}")
    else:
        print("🔧 Modo: CARGA DESDE ARCHIVO/LISTA")
        if SALE_TRANSMISSIONS_LIST:
            print(f"   • SaleTransmission desde lista: {len(SALE_TRANSMISSIONS_LIST)}")
        elif INPUT_FILE:
            print(f"   • Archivo: {INPUT_FILE}")
        else:
            print("   ⚠️  No se especificó INPUT_FILE ni SALE_TRANSMISSIONS_LIST")
        if MAX_MESSAGES and MAX_MESSAGES > 0:
            print(f"   • Máximo de mensajes: {MAX_MESSAGES}")
    print()
    print("🌐 Destino:")
    print(f"   • TARGET: {TARGET}")
    print(f"   • Ambiente: {ENVIRONMENT.upper()}")
    print(f"   • Tipo entidad: {ENTITY_TYPE}")
    print(f"   • Tipo evento: {EVENT_TYPE}")
    if TARGET in ("sqs", "both"):
        print(f"   • Cola SQS: {QUEUE_URL}")
    if TARGET in ("sns", "both"):
        print(f"   • Topic SNS: {TOPIC_ARN}")
    print(f"   • Región: {REGION}")
    print(f"   • Delay entre mensajes: {DELAY_MS}ms")
    print(f"   • Tamaño de lote: {BATCH_SIZE}")
    print(f"   • Concurrencia máxima: {MAX_CONCURRENT}")
    print()
    print(f"📝 Logs se guardan en: {LOGS_DIR}/")
    print("=" * 60)
    print()


def get_envelope_builder() -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    def builder(sale_transmission: Dict[str, Any]) -> Dict[str, Any]:
        return MessageBuilder.build_envelope(
            sale_transmission,
            entity_type='saleTransmission',
            event_type=EVENT_TYPE,
            subdomain='finmg',
            business_capacity='finmg',
            channel='web'
        )
    return builder


async def send_in_batches(
    publisher,
    items: List[Dict[str, Any]],
    batch_size: int,
    verbose: bool = False,
) -> tuple[int, int, List[str]]:
    total = len(items)
    ok_count = 0
    error_count = 0
    sii_folios_sent = []
    batches = [items[i:i + batch_size] for i in range(0, total, batch_size)]
    total_batches = len(batches)
    print(f"📦 Dividido en {total_batches} lote(s) de hasta {batch_size} mensajes cada uno\n")
    for batch_idx, batch in enumerate(batches, 1):
        batch_start = (batch_idx - 1) * batch_size + 1
        batch_end = min(batch_start + len(batch) - 1, total)
        results = await publisher.publish_batch(batch)
        for item, result in zip(batch, results):
            sii_folio = item.get("siiFolio", "UNKNOWN")
            sii_folios_sent.append(sii_folio)
            status = result.get("status")
            if status == "OK":
                ok_count += 1
            else:
                error_count += 1
                if verbose or error_count <= 5:
                    print(f"✗ ERROR - {sii_folio}: {result.get('error')}")
        if batch_idx <= 3 or batch_idx % 10 == 0 or batch_idx == total_batches:
            print(f"[Lote {batch_idx}/{total_batches}] ✓ {len(batch)} mensajes enviados (Total: {batch_end}/{total}, OK: {ok_count}, ERROR: {error_count})")
    return ok_count, error_count, sii_folios_sent


async def send_one_by_one(
    publisher,
    items: List[Dict[str, Any]],
    envelope_builder: Callable[[Dict[str, Any]], Dict[str, Any]],
    delay_ms: int = 0,
    verbose: bool = False,
) -> tuple[int, int, List[str]]:
    total = len(items)
    ok_count = 0
    error_count = 0
    sii_folios_sent = []
    for idx, item in enumerate(items, 1):
        sii_folio = item.get("siiFolio", "UNKNOWN")
        sii_folios_sent.append(sii_folio)
        if verbose and idx <= 3:
            envelope = envelope_builder(item)
            print(f"\n[{idx}/{total}] === VERIFICACIÓN DEL ENVELOPE ===")
            print(f"SiiFolio: {sii_folio}")
            print(f"Message es string: {isinstance(envelope.get('Message'), str)}")
            print(
                f"MessageAttributes.eventType.Value: {envelope.get('MessageAttributes', {}).get('eventType', {}).get('Value')}"
            )
            print("===============================")
        result = await publisher.publish_batch([item])
        status = result[0].get("status")
        if status == "OK":
            ok_count += 1
            if idx <= 10 or idx % 100 == 0 or idx == total:
                print(f"[{idx}/{total}] ✓ OK - {sii_folio}")
        else:
            error_count += 1
            print(f"[{idx}/{total}] ✗ ERROR - {sii_folio}: {result[0].get('error')}")
        if delay_ms > 0 and idx < total:
            await asyncio.sleep(delay_ms / 1000.0)
    return ok_count, error_count, sii_folios_sent


def generate_log_filename() -> str:
    logs_path = Path(LOGS_DIR)
    logs_path.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"sii_folios_{timestamp}.json"
    return str(logs_path / filename)


def save_sii_folios_log(sii_folios: List[str]) -> str:
    log_file = generate_log_filename()
    log_data = {
        "total": len(sii_folios),
        "siiFolios": sii_folios,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)
    print(f"✓ SiiFolios guardados en: {log_file}")
    return log_file


if __name__ == "__main__":
    main()

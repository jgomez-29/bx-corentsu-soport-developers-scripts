"""
Script orquestador para reenvío de notificaciones.

Flujo:
    1. Lee el CSV de errores de notificación → extrae orderIds
    2. Por cada orderId:
        a. Consulta la colección "orders" → obtiene billing.siiFolio
        b. Consulta la colección "invoices" con { siiFolio, relatedElements.identifier: orderId }
           → obtiene siiDocumentPath y totalDetail.totalToPay
        c. Construye el payload de notificación
        d. Llama a la API de envío de correos
    3. Genera un log con el resultado

Uso:
    python run_resend.py
"""

import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

# ── Resolver raíz del repo (donde está common/) ──────────────────────────────
current_path = Path(__file__).parent
while current_path != current_path.parent:
    if (current_path / "common").exists():
        repo_root = current_path
        break
    current_path = current_path.parent
else:
    raise RuntimeError("No se encontró el directorio con el módulo 'common/'")

sys.path.insert(0, str(repo_root))

# ── Cargar .env de la raíz del repo ──────────────────────────────────────────
_env_file = repo_root / ".env"
try:
    from dotenv import load_dotenv
    load_dotenv(str(_env_file))
except ImportError:
    pass
# Fallback: si dotenv no está instalado, cargar .env manualmente
if _env_file.exists() and (not os.environ.get("MONGO_URI") or not os.environ.get("MONGO_DATABASE")):
    with open(_env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                key, val = key.strip(), val.strip().strip('"').strip("'")
                if key and val:
                    os.environ[key] = val

# ── Imports del proyecto ──────────────────────────────────────────────────────

# common/ se importa desde repo_root (ya está en sys.path)
from common.mongo.mongo_client import MongoConnection

# Módulos locales del script: se importan relativo al directorio del script
# (los folders database-scripts/ y notification-resend/ tienen guiones,
#  no son válidos como nombres de módulos Python)
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

import config
from services.csv_reader import (
    read_notification_errors,
    get_unique_order_ids,
    read_failed_from_log,
)
from services.notification_client import (
    send_notification,
)
from repositories.order_repository import (
    COLLECTION_NAME as ORDERS_COLLECTION,
    find_order_by_order_id,
    extract_sii_folio,
    extract_buyer_email,
)
from repositories.invoice_repository import (
    COLLECTION_NAME as INVOICES_COLLECTION,
    find_invoice_by_folio_and_order,
    extract_document_path,
    extract_total_to_pay,
)
from entities.notification_request import (
    build_notification_request,
    NOTIFICATION_HEADERS,
)


# ============================================================================
# PROMPTS INTERACTIVOS
# ============================================================================

def prompt_yes_no(message: str, default: bool) -> bool:
    """Pregunta y/n al usuario. Enter = valor por defecto."""
    hint = "Y/n" if default else "y/N"
    while True:
        resp = input(f"{message} [{hint}]: ").strip().lower()
        if not resp:
            return default
        if resp in ("y", "yes"):
            return True
        if resp in ("n", "no"):
            return False
        print("  Enter y or n.")


def prompt_int(message: str, default: int, min_val: int = 0) -> int:
    """Pide un número entero al usuario. Enter = valor por defecto."""
    while True:
        resp = input(f"{message} [{default}]: ").strip()
        if not resp:
            return default
        try:
            val = int(resp)
            if val >= min_val:
                return val
            print(f"  Debe ser >= {min_val}.")
        except ValueError:
            print("  Ingresa un número entero.")


def prompt_string(message: str, default: str) -> str:
    """Pide un texto al usuario. Enter = valor por defecto."""
    display = default if default else "(vacío)"
    resp = input(f"{message} [{display}]: ").strip()
    return resp if resp else default


def collect_user_input():
    """
    Pide al usuario las opciones clave por terminal.
    Sobreescribe los valores en config con lo que el usuario elija.
    """
    if not sys.stdin.isatty():
        # No es terminal interactiva, usar valores de config.py tal cual
        return

    print("\n--- Configuración de ejecución ---\n")

    # 1. ¿Modo retry?
    config.RETRY_FAILED = prompt_yes_no(
        "¿Reintentar fallidos de una ejecución anterior?",
        config.RETRY_FAILED,
    )

    if config.RETRY_FAILED:
        # Listar logs disponibles y dejar seleccionar por número
        logs_dir = resolve_path(config.LOGS_DIR)
        available_logs = sorted(logs_dir.glob("resend_*.json"), reverse=True)

        if available_logs:
            print(f"\n  Logs disponibles en {config.LOGS_DIR}/:")
            for i, log_file in enumerate(available_logs[:10], 1):
                print(f"    {i}. {log_file.name}")
            print()

            while True:
                resp = input("  Selecciona el número del log a reintentar: ").strip()
                if not resp:
                    continue
                try:
                    idx = int(resp)
                    if 1 <= idx <= min(len(available_logs), 10):
                        config.RETRY_FILE = str(available_logs[idx - 1])
                        break
                    print(f"  Ingresa un número entre 1 y {min(len(available_logs), 10)}.")
                except ValueError:
                    print("  Ingresa un número válido.")
        else:
            print("\n  No hay logs disponibles en logs/.")
            config.RETRY_FILE = prompt_string(
                "Ruta manual al JSON de log",
                config.RETRY_FILE,
            )
            if config.RETRY_FILE and not Path(config.RETRY_FILE).is_absolute():
                config.RETRY_FILE = str(resolve_path(config.RETRY_FILE))

    # 2. ¿Dry run?
    config.DRY_RUN = prompt_yes_no(
        f"¿Modo DRY_RUN? (envía a {config.DRY_RUN_EMAIL} en vez del buyer.email real)",
        config.DRY_RUN,
    )

    if config.DRY_RUN:
        config.DRY_RUN_EMAIL = prompt_string(
            "Email destino para pruebas",
            config.DRY_RUN_EMAIL,
        )
        config.DRY_RUN_LIMIT = prompt_int(
            "Cantidad de registros a procesar (0 = todos)",
            config.DRY_RUN_LIMIT,
            min_val=0,
        )

    print()


# ============================================================================
# FUNCIÓN PRINCIPAL
# ============================================================================

def main():
    # Prompts interactivos (si la terminal es interactiva)
    collect_user_input()

    # Validar variables de entorno
    if not config.MONGO_URI:
        raise ValueError(
            "MONGO_URI no está definida. Agrégala en el archivo .env de la raíz del repo.\n"
            f"  Ruta esperada: {repo_root / '.env'}\n"
            "  Ejemplo: MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/"
        )

    if not config.MONGO_DATABASE:
        raise ValueError(
            "MONGO_DATABASE no está definida. Agrégala en el archivo .env de la raíz del repo.\n"
            f"  Ruta esperada: {repo_root / '.env'}\n"
            "  Ejemplo: MONGO_DATABASE=soport-orders"
        )

    # Mostrar resumen y pedir confirmación
    print_configuration()

    # 1. Obtener orderIds (desde CSV o desde JSON de retry)
    if config.RETRY_FAILED:
        if not config.RETRY_FILE:
            raise ValueError(
                "RETRY_FAILED=True pero RETRY_FILE está vacío.\n"
                "  Indica la ruta al JSON de log, ej: RETRY_FILE='./logs/resend_20260206_143000.json'"
            )
        retry_path = resolve_path(config.RETRY_FILE)
        print(f"[RETRY] Leyendo fallidos de: {retry_path}")
        order_ids = read_failed_from_log(str(retry_path))
        print(f"  → {len(order_ids)} orderIds fallidos encontrados\n")
    else:
        csv_path = resolve_path(config.CSV_FILE)
        print(f"Leyendo CSV: {csv_path}")
        records = read_notification_errors(str(csv_path))
        order_ids = get_unique_order_ids(records)
        print(f"  → {len(records)} registros leídos, {len(order_ids)} orderIds únicos\n")

    if not order_ids:
        print("No hay orderIds para procesar. Abortando.")
        return

    # Aplicar límite en modo DRY_RUN
    total_csv = len(order_ids)
    if config.DRY_RUN and config.DRY_RUN_LIMIT > 0:
        order_ids = order_ids[:config.DRY_RUN_LIMIT]
        print(f"  [DRY_RUN] Limitado a {len(order_ids)} de {total_csv} orderIds (DRY_RUN_LIMIT={config.DRY_RUN_LIMIT})\n")

    # Confirmación antes de ejecutar
    if sys.stdin.isatty():
        print(f"Se procesarán {len(order_ids)} orderIds.")
        if not config.DRY_RUN:
            print("  *** MODO REAL: se enviarán correos a los buyer.email reales ***")
        confirm = prompt_yes_no("¿Confirmar ejecución?", True)
        if not confirm:
            print("\nEjecución cancelada por el usuario.")
            return
        print()

    # 2. Conectar a MongoDB y procesar
    results = []

    _uri_display = config.MONGO_URI.split("@")[-1] if "@" in config.MONGO_URI else config.MONGO_URI
    print(f"Conectando a MongoDB: ...@{_uri_display} / {config.MONGO_DATABASE}\n")

    with MongoConnection(uri=config.MONGO_URI, database=config.MONGO_DATABASE) as db:
        orders_col = db[ORDERS_COLLECTION]
        invoices_col = db[INVOICES_COLLECTION]

        for idx, order_id in enumerate(order_ids, 1):
            result = process_order(
                idx=idx,
                total=len(order_ids),
                order_id=order_id,
                orders_col=orders_col,
                invoices_col=invoices_col,
            )
            results.append(result)

            if config.DELAY_MS > 0 and idx < len(order_ids):
                time.sleep(config.DELAY_MS / 1000.0)

    # 3. Resumen y log
    print_summary(results)
    save_log(results)


def process_order(idx, total, order_id, orders_col, invoices_col):
    """Procesa un orderId: consulta DB, construye payload, envía notificación."""
    prefix = f"[{idx}/{total}]"
    result = {"order_id": order_id, "status": "PENDING"}

    # 2a. Buscar orden
    order = find_order_by_order_id(orders_col, order_id)
    if not order:
        print(f"{prefix} ✗ Orden no encontrada: {order_id}")
        result["status"] = "ORDER_NOT_FOUND"
        return result

    sii_folio = extract_sii_folio(order)
    if not sii_folio:
        print(f"{prefix} ✗ Sin siiFolio en billing: {order_id}")
        result["status"] = "NO_SII_FOLIO"
        return result

    buyer_email = extract_buyer_email(order)
    if not buyer_email and not config.DRY_RUN:
        print(f"{prefix} ✗ Sin buyer.email en orden: {order_id}")
        result["status"] = "NO_BUYER_EMAIL"
        return result

    result["sii_folio"] = sii_folio
    result["buyer_email"] = buyer_email

    # 2b. Buscar factura
    invoice = find_invoice_by_folio_and_order(invoices_col, sii_folio, order_id)
    if not invoice:
        print(f"{prefix} ✗ Factura no encontrada: siiFolio={sii_folio}, orderId={order_id}")
        result["status"] = "INVOICE_NOT_FOUND"
        return result

    document_path = extract_document_path(invoice)
    total_to_pay = extract_total_to_pay(invoice)

    if not document_path:
        print(f"{prefix} ✗ Sin siiDocumentPath en factura: {order_id}")
        result["status"] = "NO_DOCUMENT_PATH"
        return result

    if total_to_pay is None:
        print(f"{prefix} ✗ Sin totalToPay en factura: {order_id}")
        result["status"] = "NO_TOTAL_TO_PAY"
        return result

    result["sii_document_path"] = document_path
    result["total_to_pay"] = total_to_pay

    # Determinar email destino: DRY_RUN → email quemado, normal → buyer.email
    recipient_email = config.DRY_RUN_EMAIL if config.DRY_RUN else buyer_email
    result["recipient_email"] = recipient_email

    # 2c. Construir payload
    payload = build_notification_request(
        order_id=order_id,
        sii_document_path=document_path,
        total_to_pay=total_to_pay,
        recipient_email=recipient_email,
        template_name=config.TEMPLATE_NAME,
        from_address=config.FROM_ADDRESS,
    )

    # 2d. Enviar notificación
    mode_label = "[DRY_RUN]" if config.DRY_RUN else "[PROD]"

    api_result = send_notification(
        base_url=config.NOTIFICATION_API_BASE_URL,
        payload=payload,
        headers=NOTIFICATION_HEADERS,
    )

    result["api_status"] = api_result["status"]
    result["api_status_code"] = api_result.get("status_code")

    if api_result["status"] == "OK":
        print(f"{prefix} {mode_label} ✓ Enviada: orderId={order_id} → {recipient_email}")
        result["status"] = "SENT"
    else:
        print(f"{prefix} {mode_label} ✗ Error API: orderId={order_id} → {api_result.get('error', 'Unknown')}")
        result["status"] = "API_ERROR"
        result["error"] = api_result.get("error")

    return result


# ============================================================================
# FUNCIONES DE UTILIDAD
# ============================================================================

def resolve_path(relative_path: str) -> Path:
    """Resuelve una ruta relativa al directorio del script."""
    p = Path(relative_path)
    if not p.is_absolute():
        return script_dir / relative_path
    return p


def print_configuration():
    print("=" * 60)
    print("=== REENVÍO DE NOTIFICACIONES ===")
    print("=" * 60)
    _uri_safe = "...@" + config.MONGO_URI.split("@")[-1] if "@" in config.MONGO_URI else config.MONGO_URI
    print(f"   • MongoDB URI:  {_uri_safe}")
    print(f"   • Database:     {config.MONGO_DATABASE}")
    print(f"   • Collections:  {ORDERS_COLLECTION}, {INVOICES_COLLECTION}")
    print(f"   • API Base URL: {config.NOTIFICATION_API_BASE_URL}")
    print(f"   • Template:     {config.TEMPLATE_NAME}")
    if config.RETRY_FAILED:
        print(f"   • Modo:         RETRY (reintento de fallidos)")
        print(f"   • Retry File:   {config.RETRY_FILE}")
    else:
        print(f"   • Modo:         NORMAL (desde CSV)")
        print(f"   • CSV:          {config.CSV_FILE}")
    print(f"   • Delay:        {config.DELAY_MS}ms")
    print(f"   • Dry Run:      {config.DRY_RUN}")
    if config.DRY_RUN:
        print(f"   • DRY_RUN Email:{config.DRY_RUN_EMAIL} (reemplaza buyer.email)")
        limit_label = str(config.DRY_RUN_LIMIT) if config.DRY_RUN_LIMIT > 0 else "sin límite"
        print(f"   • DRY_RUN Limit:{limit_label}")
    else:
        print(f"   • Email:        buyer.email de cada orden (real)")
    print("=" * 60)
    print()


def print_summary(results):
    total = len(results)
    sent = sum(1 for r in results if r["status"] == "SENT")
    errors = total - sent

    print()
    print("=" * 50)
    print("=== RESUMEN FINAL ===")
    print(f"   Total procesados:    {total}")
    print(f"   Enviados:            {sent}")
    print(f"   Errores/No enviados: {errors}")
    if config.DRY_RUN:
        print(f"   (Enviados a: {config.DRY_RUN_EMAIL})")
    print("=" * 50)


def save_log(results):
    logs_dir = resolve_path(config.LOGS_DIR)
    logs_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = logs_dir / f"resend_{timestamp}.json"

    log_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "retry": config.RETRY_FAILED,
        "retry_source": str(resolve_path(config.RETRY_FILE)) if config.RETRY_FAILED else None,
        "dry_run": config.DRY_RUN,
        "dry_run_email": config.DRY_RUN_EMAIL if config.DRY_RUN else None,
        "total": len(results),
        "sent": sum(1 for r in results if r["status"] == "SENT"),
        "errors": sum(1 for r in results if r["status"] != "SENT"),
        "results": results,
    }

    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)

    print(f"\nLog guardado en: {log_file}")


if __name__ == "__main__":
    main()

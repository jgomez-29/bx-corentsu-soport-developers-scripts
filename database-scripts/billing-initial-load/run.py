"""
Script orquestador: carga inicial de facturación (billing-initial-load).

Flujo:
    1. Pide al usuario fechas de inicio y término + opciones DRY_RUN.
    2. Itera día a día el rango [start_date, end_date).
    3. Por cada día: obtiene cursor de OS candidatas desde MongoDB (batch_size=1000).
    4. Acumula lotes de hasta BATCH_SIZE órdenes y llama a billing_service.
    5. Muestra progreso en consola y genera log JSON al finalizar.

Uso:
    python ./database-scripts/billing-initial-load/run.py
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── Resolver raíz del repo (donde está common/) ──────────────────────────────
current_path = Path(__file__).parent
while current_path != current_path.parent:
    if (current_path / "common").exists():
        repo_root = current_path
        break
    current_path = current_path.parent
else:
    raise RuntimeError("No se encontró el directorio con el módulo 'common/'")

script_dir = Path(__file__).parent
sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(script_dir))

# ── Cargar .env de la raíz del repo ──────────────────────────────────────────
_env_file = repo_root / ".env"
try:
    from dotenv import load_dotenv
    load_dotenv(str(_env_file))
except ImportError:
    pass

if _env_file.exists() and (not os.environ.get("MONGO_URI") or not os.environ.get("ORACLE_DSN")):
    with open(_env_file, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _, _val = _line.partition("=")
                _key, _val = _key.strip(), _val.strip().strip('"').strip("'")
                if _key and _val:
                    os.environ[_key] = _val

# ── Imports del proyecto ──────────────────────────────────────────────────────
from common.mongo.mongo_client import MongoConnection
from common.oracle.oracle_client import OracleConnection

import config
from repositories.order_repository import COLLECTION_NAME as ORDERS_COLLECTION
from services import billing_service


# ============================================================================
# PROMPTS INTERACTIVOS
# ============================================================================


def prompt_yes_no(message: str, default: bool) -> bool:
    hint = "S/n" if default else "s/N"
    while True:
        resp = input(f"{message} [{hint}]: ").strip().lower()
        if not resp:
            return default
        if resp in ("s", "si", "sí", "y", "yes"):
            return True
        if resp in ("n", "no"):
            return False
        print("  Ingresa s o n.")


def prompt_int(message: str, default: int, min_val: int = 0) -> int:
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


def prompt_date(message: str, default: str) -> str:
    while True:
        display = default if default else "YYYY-MM-DD"
        resp = input(f"{message} [{display}]: ").strip()
        if not resp and default:
            return default
        try:
            datetime.strptime(resp, "%Y-%m-%d")
            return resp
        except ValueError:
            print("  Formato inválido. Usa YYYY-MM-DD (ej: 2026-01-01).")


# ============================================================================
# FUNCIONES DE UTILIDAD
# ============================================================================


def resolve_path(relative_path: str) -> Path:
    p = Path(relative_path)
    if not p.is_absolute():
        return script_dir / relative_path
    return p


def day_ranges(start_date: str, end_date: str):
    """Genera tuplas (day_start UTC, day_end UTC) para cada día del rango."""
    current = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    while current < end:
        yield current, current + timedelta(days=1)
        current += timedelta(days=1)


def collect_user_input():
    """Recopila opciones del usuario.

    Si hay fechas configuradas en config.py, pregunta si desea usarlas.
    Si el usuario elige no usarlas (o no hay fechas configuradas), solicita un rango custom.
    DRY_RUN y límite sólo se preguntan si la terminal es interactiva.
    """
    interactive = sys.stdin.isatty()

    print("\n=== billing-initial-load ===\n")

    # ── Fechas ────────────────────────────────────────────────────────────────
    has_configured_dates = bool(config.START_DATE and config.END_DATE)

    if has_configured_dates and interactive:
        print(f"  Rango configurado: {config.START_DATE} → {config.END_DATE}")
        use_configured = prompt_yes_no("¿Usar el rango de fechas configurado?", True)
        if not use_configured:
            config.START_DATE = prompt_date("¿Fecha de inicio? (YYYY-MM-DD)", "")
            config.END_DATE = prompt_date("¿Fecha de término? (YYYY-MM-DD)", "")
    else:
        config.START_DATE = prompt_date("¿Fecha de inicio? (YYYY-MM-DD)", config.START_DATE or "")
        config.END_DATE = prompt_date("¿Fecha de término? (YYYY-MM-DD)", config.END_DATE or "")

    # ── DRY_RUN (solo si terminal interactiva) ────────────────────────────────
    if interactive:
        config.DRY_RUN = prompt_yes_no("¿Activar modo DRY_RUN?", config.DRY_RUN)
        if config.DRY_RUN:
            config.DRY_RUN_LIMIT = prompt_int(
                "¿Límite DRY_RUN (registros por día, 0 = sin límite)?",
                config.DRY_RUN_LIMIT,
                min_val=0,
            )

    print()


def validate_config():
    """Valida variables de entorno requeridas."""
    for var in ("MONGO_URI", "MONGO_DATABASE", "ORACLE_DSN", "ORACLE_USER", "ORACLE_PASSWORD"):
        if not getattr(config, var, None):
            raise ValueError(
                f"{var} no está definida. Agrégala en el archivo .env de la raíz del repo.\n"
                f"  Ruta esperada: {repo_root / '.env'}"
            )
    if not config.START_DATE:
        raise ValueError("START_DATE no está definida. Ingresa una fecha de inicio (YYYY-MM-DD).")
    if not config.END_DATE:
        raise ValueError("END_DATE no está definida. Ingresa una fecha de término (YYYY-MM-DD).")

    start_dt = datetime.strptime(config.START_DATE, "%Y-%m-%d")
    end_dt = datetime.strptime(config.END_DATE, "%Y-%m-%d")
    if start_dt >= end_dt:
        raise ValueError(
            f"La fecha de inicio ({config.START_DATE}) debe ser anterior a la fecha de término ({config.END_DATE})."
        )


def print_initial_summary(total_days: int):
    print("=" * 65)
    print("=== RESUMEN INICIAL: billing-initial-load ===")
    print("=" * 65)
    print(f"  Rango         : {config.START_DATE} → {config.END_DATE} ({total_days} días)")
    print(f"  Modo          : {'DRY_RUN (sin escrituras)' if config.DRY_RUN else '⚠  REAL (escribirá en MongoDB)'}")
    if config.DRY_RUN and config.DRY_RUN_LIMIT > 0:
        print(f"  Límite/día    : {config.DRY_RUN_LIMIT} registros")
    print(f"  Tamaño lote   : {config.BATCH_SIZE} OS")
    _uri_safe = ("...@" + config.MONGO_URI.split("@")[-1] if "@" in config.MONGO_URI else config.MONGO_URI)
    print(f"  MongoDB       : {_uri_safe} / {config.MONGO_DATABASE}")
    print(f"  Oracle DSN    : {config.ORACLE_DSN}")
    print(f"  Colecciones   : orders, proformas, proformaRequests, invoices")
    print("=" * 65)
    print()


def confirm_execution():
    """Pide confirmación antes de ejecutar en modo real."""
    if not sys.stdin.isatty() or config.DRY_RUN:
        return
    print("⚠  Modo REAL: se realizarán escrituras en MongoDB.")
    if not prompt_yes_no("¿Confirmar ejecución?", False):
        print("\nEjecución cancelada por el usuario.")
        sys.exit(0)
    print()


def print_final_summary(stats: dict, elapsed: float):
    total_updated = stats["updated_with_proforma"] + stats["updated_without_proforma"]
    rate = total_updated / elapsed if elapsed > 0 else 0
    h, rem = divmod(int(elapsed), 3600)
    m, s = divmod(rem, 60)
    elapsed_str = f"{h:02d}:{m:02d}:{s:02d}"

    print()
    print("=" * 65)
    print("=== RESUMEN FINAL ===")
    print(f"  Días procesados         : {stats['days']}")
    print(f"  OS candidatas           : {stats['total_candidates']}")
    print(f"  Actualizadas (c/proforma): {stats['updated_with_proforma']}")
    print(f"  Actualizadas (s/proforma): {stats['updated_without_proforma']}")
    print(f"  Skipped (ya BILLED)     : {stats['skipped_already_billed']}")
    print(f"  Skipped (sin taxDoc)    : {stats['skipped_no_tax_doc']}")
    print(f"  Errores                 : {stats['errors']}")
    print(f"  Proformas creadas       : {stats['proformas_created']}")
    print(f"  Invoices creadas        : {stats['invoices_created']}")
    if config.DRY_RUN:
        print(f"  (Modo DRY_RUN: sin escrituras)")
    print(f"  Throughput              : {rate:.1f} OS/s")
    print(f"  Tiempo total            : {elapsed_str}")
    print("=" * 65)


def save_log(stats: dict, all_results: list, elapsed: float):
    logs_dir = resolve_path(config.LOGS_DIR)
    logs_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = logs_dir / f"billing-initial-load_{timestamp}.json"

    log_data = {
        "started_at": stats["started_at"],
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": round(elapsed, 2),
        "dry_run": config.DRY_RUN,
        "date_range": {"from": config.START_DATE, "to": config.END_DATE},
        "summary": {
            "days_processed": stats["days"],
            "total_candidates": stats["total_candidates"],
            "updated": stats["updated_with_proforma"] + stats["updated_without_proforma"],
            "updated_with_proforma": stats["updated_with_proforma"],
            "updated_without_proforma": stats["updated_without_proforma"],
            "skipped_already_billed": stats["skipped_already_billed"],
            "skipped_no_tax_doc": stats["skipped_no_tax_doc"],
            "errors": stats["errors"],
            "proformas_created": stats["proformas_created"],
            "invoices_created": stats["invoices_created"],
        },
        "results": all_results,
    }

    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False, default=str)

    print(f"\nLog guardado en: {log_file}")


# ============================================================================
# FUNCIÓN PRINCIPAL
# ============================================================================


def main():
    collect_user_input()
    validate_config()

    days = list(day_ranges(config.START_DATE, config.END_DATE))
    total_days = len(days)

    print_initial_summary(total_days)
    confirm_execution()

    stats = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "days": 0,
        "total_candidates": 0,
        "updated_with_proforma": 0,
        "updated_without_proforma": 0,
        "skipped_already_billed": 0,
        "skipped_no_tax_doc": 0,
        "errors": 0,
        "proformas_created": 0,
        "invoices_created": 0,
    }
    all_results = []
    start_time = time.monotonic()

    with MongoConnection(uri=config.MONGO_URI, database=config.MONGO_DATABASE) as mongo_db:
        with OracleConnection(
            dsn=config.ORACLE_DSN,
            user=config.ORACLE_USER,
            password=config.ORACLE_PASSWORD,
        ) as oracle_conn:

            for day_idx, (day_start, day_end) in enumerate(days, 1):
                day_label = day_start.strftime("%Y-%m-%d")
                day_pct = day_idx / total_days * 100
                print(f"\n[Día {day_idx}/{total_days}] ({day_pct:.0f}%) {day_label} → {day_end.strftime('%Y-%m-%d')}")

                orders_col = mongo_db[ORDERS_COLLECTION]

                day_filter = {
                    "emissionDate": {"$gte": day_start, "$lt": day_end},
                    "taxDocument": {"$exists": True, "$ne": None},
                    "billing.status": {"$ne": "BILLED"},
                }
                day_total = orders_col.count_documents(day_filter)
                print(f"  OS candidatas del día : {day_total}")

                cursor = orders_col.find(
                    day_filter,
                    {
                        "orderId": 1,
                        "emissionDate": 1,
                        "referenceOrder": 1,
                        "seller.account": 1,
                        "taxDocument": 1,
                        "billing": 1,
                    },
                    batch_size=config.BATCH_SIZE,
                )

                batch = []
                day_processed = 0
                day_updated = 0
                day_errors = 0
                batch_num = 0
                day_limit_reached = False

                for doc in cursor:
                    if config.DRY_RUN and config.DRY_RUN_LIMIT > 0:
                        if day_processed >= config.DRY_RUN_LIMIT:
                            day_limit_reached = True
                            break

                    batch.append(doc)
                    day_processed += 1

                    if len(batch) >= config.BATCH_SIZE:
                        batch_num += 1
                        try:
                            batch_results = billing_service.process_batch(
                                batch, mongo_db, oracle_conn, config.DRY_RUN
                            )
                        except Exception as e:
                            print(f"  [ERROR] Lote {batch_num}: {e}")
                            for order in batch:
                                all_results.append({
                                    "orderId": order.get("orderId", ""),
                                    "status": "ERROR",
                                    "reason": str(e),
                                })
                            stats["errors"] += len(batch)
                            day_errors += len(batch)
                            batch = []
                            continue

                        _accumulate(stats, batch_results)
                        all_results.extend(batch_results)
                        day_updated += sum(1 for r in batch_results if r["status"] in ("UPDATED", "UPDATED_WITHOUT_PROFORMA", "DRY_RUN"))
                        day_errors += sum(1 for r in batch_results if r["status"] == "ERROR")

                        elapsed = time.monotonic() - start_time
                        rate = stats["updated_with_proforma"] + stats["updated_without_proforma"]
                        rate_per_s = rate / elapsed if elapsed > 0 else 0
                        day_progress_pct = day_processed / day_total * 100 if day_total > 0 else 0
                        print(
                            f"  Lote {batch_num} | {day_processed}/{day_total} OS ({day_progress_pct:.0f}%) | "
                            f"{day_updated} actualizadas | {day_errors} errores | "
                            f"{rate_per_s:.1f} OS/s"
                        )
                        batch = []

                # Procesar el lote restante del día
                if batch:
                    batch_num += 1
                    try:
                        batch_results = billing_service.process_batch(
                            batch, mongo_db, oracle_conn, config.DRY_RUN
                        )
                    except Exception as e:
                        print(f"  [ERROR] Lote {batch_num} (final): {e}")
                        for order in batch:
                            all_results.append({
                                "orderId": order.get("orderId", ""),
                                "status": "ERROR",
                                "reason": str(e),
                            })
                        stats["errors"] += len(batch)
                        day_errors += len(batch)
                        batch_results = []

                    if batch_results:
                        _accumulate(stats, batch_results)
                        all_results.extend(batch_results)
                        day_updated += sum(1 for r in batch_results if r["status"] in ("UPDATED", "UPDATED_WITHOUT_PROFORMA", "DRY_RUN"))

                day_progress_pct = day_processed / day_total * 100 if day_total > 0 else 0
                limit_note = f" (límite DRY_RUN {config.DRY_RUN_LIMIT})" if day_limit_reached else ""
                print(f"  → {day_processed}/{day_total} OS procesadas ({day_progress_pct:.0f}%) | {day_updated} actualizadas{limit_note}")
                stats["days"] += 1

    elapsed = time.monotonic() - start_time
    print_final_summary(stats, elapsed)
    save_log(stats, all_results, elapsed)


def _accumulate(stats: dict, batch_results: list):
    """Acumula métricas de un lote en el diccionario de stats global."""
    for r in batch_results:
        status = r.get("status", "")
        if status == "UPDATED":
            stats["updated_with_proforma"] += 1
            stats["total_candidates"] += 1
        elif status == "UPDATED_WITHOUT_PROFORMA":
            stats["updated_without_proforma"] += 1
            stats["total_candidates"] += 1
        elif status == "DRY_RUN":
            if r.get("proforma_action") in ("FOUND", "CREATED"):
                stats["updated_with_proforma"] += 1
            else:
                stats["updated_without_proforma"] += 1
            stats["total_candidates"] += 1
        elif status == "SKIPPED_ALREADY_BILLED":
            stats["skipped_already_billed"] += 1
        elif status == "SKIPPED_NO_TAX_DOCUMENT":
            stats["skipped_no_tax_doc"] += 1
        elif status == "ERROR":
            stats["errors"] += 1

        if r.get("proforma_action") == "CREATED":
            stats["proformas_created"] += 1
        if r.get("invoice_action") == "CREATED":
            stats["invoices_created"] += 1


if __name__ == "__main__":
    main()

"""
Modo taxDocument: carga inicial de facturación por rango de fechas.

Filtra órdenes de servicio que tengan taxDocument presente y billing.status != BILLED,
acotadas a las cuentas del archivo configurado.

Flujo:
    1. Itera día a día el rango [start_date, end_date) (inputs ya recopilados por run.py).
    2. Por cada día divide las cuentas en lotes (ACCOUNT_BATCH_SIZE) y lanza
       un cursor por lote usando el índice seller.account + emissionDate.
    3. Acumula lotes de hasta BATCH_SIZE órdenes y llama a billing_service.
    4. Muestra progreso en consola y genera log JSON al finalizar.
"""

import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

_SCRIPT_DIR = Path(__file__).parent.parent  # billing-initial-load/

import config
from common.mongo.mongo_client import MongoConnection
from common.oracle.oracle_client import OracleConnection
from repositories.order_repository import COLLECTION_NAME as ORDERS_COLLECTION
from services import billing_service


# ============================================================================
# UTILIDADES ESPECÍFICAS DEL MODO
# ============================================================================


def _chunks(lst: list, size: int):
    """Divide una lista en sublistas de hasta `size` elementos."""
    for i in range(0, len(lst), size):
        yield lst[i: i + size]


def _day_ranges(start_date: str, end_date: str):
    """Genera tuplas (day_start UTC, day_end UTC) para cada día del rango."""
    current = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    while current < end:
        yield current, current + timedelta(days=1)
        current += timedelta(days=1)


def _resolve_path(relative_path: str) -> Path:
    p = Path(relative_path)
    return p if p.is_absolute() else _SCRIPT_DIR / relative_path


# ============================================================================
# RESUMEN Y LOG
# ============================================================================


def _print_initial_summary(total_days: int):
    print("=" * 65)
    print("=== RESUMEN INICIAL: billing-initial-load [taxDocument] ===")
    print("=" * 65)
    print(f"  Rango         : {config.START_DATE} → {config.END_DATE} ({total_days} días)")
    print(f"  Modo          : {'DRY_RUN (sin escrituras)' if config.DRY_RUN else '⚠  REAL (escribirá en MongoDB)'}")
    if config.DRY_RUN and config.DRY_RUN_LIMIT > 0:
        print(f"  Límite/día    : {config.DRY_RUN_LIMIT} registros")
    print(f"  Tamaño lote   : {config.BATCH_SIZE} OS")
    print(f"  Cuentas       : {len(config.ACCOUNTS_FILTER)} ({config.ACCOUNTS_FILE})")
    _uri_safe = ("...@" + config.MONGO_URI.split("@")[-1] if "@" in config.MONGO_URI else config.MONGO_URI)
    print(f"  MongoDB       : {_uri_safe} / {config.MONGO_DATABASE}")
    print(f"  Oracle DSN    : {config.ORACLE_DSN}")
    print(f"  Colecciones   : orders, proformas, proformaRequests, invoices")
    print("=" * 65)
    print()


def _confirm_execution():
    """Pide confirmación antes de ejecutar en modo real."""
    if not sys.stdin.isatty() or config.DRY_RUN:
        return
    from run import prompt_yes_no
    print("⚠  Modo REAL: se realizarán escrituras en MongoDB.")
    if not prompt_yes_no("¿Confirmar ejecución?", False):
        print("\nEjecución cancelada por el usuario.")
        sys.exit(0)
    print()


def _print_final_summary(stats: dict, elapsed: float):
    total_updated = stats["updated_with_proforma"] + stats["updated_without_proforma"]
    rate = total_updated / elapsed if elapsed > 0 else 0
    h, rem = divmod(int(elapsed), 3600)
    m, s = divmod(rem, 60)
    elapsed_str = f"{h:02d}:{m:02d}:{s:02d}"

    print()
    print("=" * 65)
    print("=== RESUMEN FINAL ===")
    print(f"  Días procesados         : {stats['days']}")
    print(f"  OS candidatas (cursor)  : {stats['total_candidates']}")
    print(f"  Actualizadas (c/proforma): {stats['updated_with_proforma']}")
    print(f"  Actualizadas (s/proforma): {stats['updated_without_proforma']}")
    if not config.DRY_RUN:
        print(f"  Actualizadas en MongoDB : {stats['orders_modified']}  ← total real")
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


def _save_log(stats: dict, all_results: list, elapsed: float):
    logs_dir = _resolve_path(config.LOGS_DIR)
    logs_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = logs_dir / f"billing-initial-load_taxDocument_{timestamp}.json"

    log_data = {
        "mode": "taxDocument",
        "started_at": stats["started_at"],
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": round(elapsed, 2),
        "dry_run": config.DRY_RUN,
        "date_range": {"from": config.START_DATE, "to": config.END_DATE},
        "accounts_filter": {"file": config.ACCOUNTS_FILE, "accounts": config.ACCOUNTS_FILTER},
        "summary": {
            "days_processed": stats["days"],
            "total_candidates": stats["total_candidates"],
            "updated": stats["updated_with_proforma"] + stats["updated_without_proforma"],
            "updated_with_proforma": stats["updated_with_proforma"],
            "updated_without_proforma": stats["updated_without_proforma"],
            "orders_modified_in_mongo": stats["orders_modified"],
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
# ACUMULACIÓN DE MÉTRICAS
# ============================================================================


def _accumulate(stats: dict, batch_results: list):
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


# ============================================================================
# PUNTO DE ENTRADA DEL MODO
# ============================================================================


def run():
    """Ejecuta el modo taxDocument. Asume que run.py ya recopiló y validó los inputs."""
    days = list(_day_ranges(config.START_DATE, config.END_DATE))
    total_days = len(days)

    _print_initial_summary(total_days)
    _confirm_execution()

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
        "orders_modified": 0,
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

                base_filter = {
                    "emissionDate": {"$gte": day_start, "$lt": day_end},
                    "taxDocument": {"$exists": True, "$ne": None},
                    "billing.status": {"$ne": "BILLED"},
                    "seller.account": {"$in": config.ACCOUNTS_FILTER},
                }
                day_total = orders_col.count_documents(base_filter)
                account_batches = list(_chunks(config.ACCOUNTS_FILTER, config.ACCOUNT_BATCH_SIZE))
                print(f"  OS candidatas del día : {day_total}")
                print(f"  Lotes de cuentas      : {len(account_batches)} ({config.ACCOUNT_BATCH_SIZE} cuentas/lote)")

                projection = {
                    "orderId": 1,
                    "emissionDate": 1,
                    "referenceOrder": 1,
                    "seller.account": 1,
                    "taxDocument": 1,
                    "billing": 1,
                }

                batch = []
                day_processed = 0
                day_updated = 0
                day_errors = 0
                batch_num = 0
                day_limit_reached = False

                for acc_batch in account_batches:
                    if day_limit_reached:
                        break

                    acc_filter = {**base_filter, "seller.account": {"$in": acc_batch}}
                    cursor = orders_col.find(acc_filter, projection, batch_size=config.BATCH_SIZE).hint([
                        ("seller.account", 1),
                        ("emissionDate", 1),
                        ("billing.deliveryDate", 1),
                        ("billing.proformaId", 1),
                        ("state", 1),
                        ("_id", 1),
                    ])

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
                                batch_results, write_stats = billing_service.process_batch(
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
                            stats["orders_modified"] += write_stats["orders_modified"]
                            all_results.extend(batch_results)
                            if config.DRY_RUN:
                                day_updated += sum(1 for r in batch_results if r["status"] == "DRY_RUN")
                            else:
                                day_updated += write_stats["orders_modified"]
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

                # Procesar el lote restante del día (acumulado entre todos los lotes de cuentas)
                if batch:
                    batch_num += 1
                    try:
                        batch_results, write_stats = billing_service.process_batch(
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
                        write_stats = {"orders_matched": 0, "orders_modified": 0}

                    if batch_results:
                        _accumulate(stats, batch_results)
                        stats["orders_modified"] += write_stats["orders_modified"]
                        all_results.extend(batch_results)
                        if config.DRY_RUN:
                            day_updated += sum(1 for r in batch_results if r["status"] == "DRY_RUN")
                        else:
                            day_updated += write_stats["orders_modified"]

                day_progress_pct = day_processed / day_total * 100 if day_total > 0 else 0
                limit_note = f" (límite DRY_RUN {config.DRY_RUN_LIMIT})" if day_limit_reached else ""
                print(f"  → {day_processed}/{day_total} OS procesadas ({day_progress_pct:.0f}%) | {day_updated} actualizadas{limit_note}")
                stats["days"] += 1

    elapsed = time.monotonic() - start_time
    _print_final_summary(stats, elapsed)
    _save_log(stats, all_results, elapsed)

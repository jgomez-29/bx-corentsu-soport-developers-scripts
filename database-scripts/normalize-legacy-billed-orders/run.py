"""
Script de normalización de OS facturadas en legado Oracle → MongoDB.

Flujo:
    1. Solicita rango de fechas (fecha inicio y fecha fin) al operador.
    2. Consulta MongoDB colección 'orders' buscando OS sin billing.status='BILLED'
       cuya emissionDate esté en [DATE_FROM, DATE_TO), paginando por _id (keyset).
    3. Por cada lote de hasta 1000 OS, consulta Oracle tabla DCBT con
       EEVV_NMR_ID IN (...) para obtener DCBT_NMR_FAC_PF (número de proforma).
    4. Actualiza MongoDB en bulk: asigna billing.proformaId y billing.status='BILLED'.
    5. Muestra progreso por lote y resumen final con métricas.
    6. Genera log JSON en logs/ con el detalle de cada OS procesada.

Uso:
    python ./database-scripts/normalize-legacy-billed-orders/run.py
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
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

sys.path.insert(0, str(repo_root))

# ── Cargar .env de la raíz del repo ──────────────────────────────────────────
_env_file = repo_root / ".env"
try:
    from dotenv import load_dotenv
    load_dotenv(str(_env_file))
except ImportError:
    pass

if _env_file.exists() and (
    not os.environ.get("MONGO_URI") or not os.environ.get("ORACLE_DSN")
):
    with open(_env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                key, val = key.strip(), val.strip().strip('"').strip("'")
                if key and val:
                    os.environ[key] = val

# ── Imports del proyecto ──────────────────────────────────────────────────────
from common.mongo.mongo_client import MongoConnection

script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

import config
from entities.order import build_billing_update
from repositories.order_repository import (
    COLLECTION_NAME,
    find_unbilled_orders_batch,
    bulk_update_billing,
)
from services.oracle_client import OracleConnection, fetch_proforma_ids_batch


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
        if resp in ("y", "yes", "s", "si", "sí"):
            return True
        if resp in ("n", "no"):
            return False
        print("  Ingresa y o n.")


def prompt_date(message: str, default: str) -> str:
    """Pide una fecha en formato YYYY-MM-DD. Enter = valor por defecto."""
    display = default if default else "(vacío)"
    while True:
        resp = input(f"{message} [{display}]: ").strip()
        if not resp:
            return default
        try:
            datetime.strptime(resp, "%Y-%m-%d")
            return resp
        except ValueError:
            print("  Formato inválido. Usa YYYY-MM-DD (ej: 2026-01-01).")


def collect_user_input():
    """
    Solicita fecha inicio, fecha fin y modo DRY_RUN al operador.
    Sobreescribe los valores de config con las respuestas del usuario.
    Si no es terminal interactiva, usa valores de config.py tal cual.
    """
    if not sys.stdin.isatty():
        return

    print("\n--- Configuración de ejecución ---\n")

    config.DATE_FROM = prompt_date("Fecha de inicio (YYYY-MM-DD)", config.DATE_FROM)
    config.DATE_TO = prompt_date("Fecha de término (YYYY-MM-DD)", config.DATE_TO)

    config.DRY_RUN = prompt_yes_no(
        "¿Modo DRY_RUN? (simula sin modificar MongoDB)",
        config.DRY_RUN,
    )
    print()


# ============================================================================
# VALIDACIÓN
# ============================================================================


def validate_config():
    """Valida variables de entorno y parámetros de ejecución."""
    env_path = repo_root / ".env"

    if not config.MONGO_URI:
        raise ValueError(
            "MONGO_URI no está definida. Agrégala en el archivo .env de la raíz del repo.\n"
            f"  Ruta esperada: {env_path}\n"
            "  Ejemplo: MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/"
        )
    if not config.MONGO_DATABASE:
        raise ValueError(
            "MONGO_DATABASE no está definida. Agrégala en el archivo .env.\n"
            f"  Ruta esperada: {env_path}\n"
            "  Ejemplo: MONGO_DATABASE=soport-orders"
        )
    if not config.ORACLE_DSN:
        raise ValueError(
            "ORACLE_DSN no está definida. Agrégala en el archivo .env.\n"
            f"  Ruta esperada: {env_path}\n"
            "  Ejemplo: ORACLE_DSN=host:1521/service_name"
        )
    if not config.ORACLE_USER:
        raise ValueError(
            "ORACLE_USER no está definida. Agrégala en el archivo .env.\n"
            f"  Ruta esperada: {env_path}"
        )
    if not config.ORACLE_PASSWORD:
        raise ValueError(
            "ORACLE_PASSWORD no está definida. Agrégala en el archivo .env.\n"
            f"  Ruta esperada: {env_path}"
        )
    if not config.DATE_FROM:
        raise ValueError(
            "DATE_FROM no está definido. Ejecútalo en modo interactivo o define "
            "DATE_FROM en config.py (formato YYYY-MM-DD)."
        )
    if not config.DATE_TO:
        raise ValueError(
            "DATE_TO no está definido. Ejecútalo en modo interactivo o define "
            "DATE_TO en config.py (formato YYYY-MM-DD)."
        )

    date_from = datetime.strptime(config.DATE_FROM, "%Y-%m-%d")
    date_to = datetime.strptime(config.DATE_TO, "%Y-%m-%d")
    if date_from > date_to:
        raise ValueError(
            f"DATE_FROM ({config.DATE_FROM}) no puede ser posterior a "
            f"DATE_TO ({config.DATE_TO})."
        )


# ============================================================================
# PRESENTACIÓN
# ============================================================================


def print_configuration():
    """Imprime resumen inicial de configuración antes de ejecutar."""
    uri_safe = (
        "...@" + config.MONGO_URI.split("@")[-1]
        if "@" in config.MONGO_URI
        else config.MONGO_URI
    )
    mode_label = "DRY_RUN ✓ (sin cambios en MongoDB)" if config.DRY_RUN else "REAL ⚠️  (modificará MongoDB)"

    print("=" * 62)
    print("=== NORMALIZACIÓN OS FACTURADAS EN LEGADO ===")
    print("=" * 62)
    print(f"   • MongoDB URI:   {uri_safe}")
    print(f"   • Base de datos: {config.MONGO_DATABASE}")
    print(f"   • Colección:     {COLLECTION_NAME}")
    print(f"   • Oracle DSN:    {config.ORACLE_DSN}")
    print(f"   • Rango:         {config.DATE_FROM} → {config.DATE_TO}")
    print(f"   • Batch size:    {config.BATCH_SIZE}")
    print(f"   • Modo:          {mode_label}")
    print("=" * 62)
    print()


def print_batch_progress(batch_num, os_found, oracle_found, updated, not_in_legacy, already_billed, errors):
    """Imprime progreso del lote actual."""
    mode = "[DRY]" if config.DRY_RUN else "[REAL]"
    print(
        f"  {mode} Lote {batch_num:>4} | "
        f"OS: {os_found:>5} | "
        f"Oracle: {oracle_found:>5} | "
        f"Actualizadas: {updated:>5} | "
        f"No en legado: {not_in_legacy:>5} | "
        f"Ya facturadas: {already_billed:>4} | "
        f"Errores: {errors:>3}"
    )


def print_summary(results, elapsed_seconds):
    """Calcula y muestra el resumen final con métricas de ejecución."""
    total = len(results)
    updated = sum(1 for r in results if r["status"] in ("UPDATED", "DRY_RUN"))
    already_billed = sum(1 for r in results if r["status"] == "ALREADY_BILLED")
    not_in_legacy = sum(1 for r in results if r["status"] == "NOT_IN_LEGACY")
    errors = sum(1 for r in results if r["status"] == "ERROR")
    throughput = updated / elapsed_seconds if elapsed_seconds > 0 else 0.0

    print()
    print("=" * 62)
    print("=== RESUMEN FINAL ===")
    print(f"   OS encontradas:        {total:>8}")
    print(f"   OS actualizadas:       {updated:>8}  {'(simulado)' if config.DRY_RUN else ''}")
    print(f"   Ya facturadas (skip):  {already_billed:>8}")
    print(f"   No en legado (skip):   {not_in_legacy:>8}")
    print(f"   Errores:               {errors:>8}")
    print(f"   Throughput:            {throughput:>7.1f} OS/seg")
    print(f"   Tiempo total:          {elapsed_seconds:>7.1f} seg")
    print("=" * 62)


def save_log(results, elapsed_seconds):
    """Genera log JSON en logs/ con metadata y array de resultados por OS."""
    logs_dir = script_dir / config.LOGS_DIR
    logs_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = logs_dir / f"normalize_{timestamp}.json"

    total = len(results)
    updated = sum(1 for r in results if r["status"] in ("UPDATED", "DRY_RUN"))
    already_billed = sum(1 for r in results if r["status"] == "ALREADY_BILLED")
    not_in_legacy = sum(1 for r in results if r["status"] == "NOT_IN_LEGACY")
    errors = sum(1 for r in results if r["status"] == "ERROR")
    throughput = updated / elapsed_seconds if elapsed_seconds > 0 else 0.0

    log_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dry_run": config.DRY_RUN,
        "date_from": config.DATE_FROM,
        "date_to": config.DATE_TO,
        "duration_seconds": round(elapsed_seconds, 2),
        "throughput_per_second": round(throughput, 2),
        "total_found": total,
        "total_updated": updated,
        "total_already_billed": already_billed,
        "total_not_in_legacy": not_in_legacy,
        "total_errors": errors,
        "results": results,
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
    print_configuration()

    if sys.stdin.isatty() and not config.DRY_RUN:
        confirm = prompt_yes_no(
            "⚠️  Modo REAL: se modificará MongoDB. ¿Confirmar ejecución?",
            False,
        )
        if not confirm:
            print("\nEjecución cancelada por el usuario.")
            return
        print()

    date_from = datetime.strptime(config.DATE_FROM, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    date_to = datetime.strptime(config.DATE_TO, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    all_results = []
    batch_num = 0
    last_id = None
    start_time = time.time()

    print(f"Conectando a MongoDB: {config.MONGO_DATABASE} / {COLLECTION_NAME}")
    print(f"Conectando a Oracle:  {config.ORACLE_DSN}\n")

    with MongoConnection(uri=config.MONGO_URI, database=config.MONGO_DATABASE) as db:
        collection = db[COLLECTION_NAME]

        with OracleConnection(
            dsn=config.ORACLE_DSN,
            user=config.ORACLE_USER,
            password=config.ORACLE_PASSWORD,
        ) as oracle_conn:

            while True:
                # ── Leer lote de MongoDB ──────────────────────────────────
                batch = find_unbilled_orders_batch(
                    collection,
                    date_from,
                    date_to,
                    config.BATCH_SIZE,
                    last_id,
                )
                if not batch:
                    break

                batch_num += 1
                last_id = batch[-1]["_id"]

                # ── Consultar Oracle para este lote ───────────────────────
                reference_ids = [
                    str(order["referenceOrder"])
                    for order in batch
                    if order.get("referenceOrder")
                ]

                try:
                    proforma_map = fetch_proforma_ids_batch(oracle_conn, reference_ids)
                except Exception as e:
                    # Error de conectividad: registrar todo el lote como ERROR
                    for order in batch:
                        all_results.append({
                            "order_id": order.get("orderId", ""),
                            "reference_order": str(order.get("referenceOrder", "")),
                            "emission_date": str(order.get("emissionDate", "")),
                            "proforma_id": None,
                            "status": "ERROR",
                            "reason": f"Error Oracle: {e}",
                        })
                    print_batch_progress(batch_num, len(batch), 0, 0, 0, 0, len(batch))
                    continue

                # ── Clasificar cada OS del lote ───────────────────────────
                batch_results = []
                updates_to_apply = []

                for order in batch:
                    order_id = order.get("orderId", "")
                    ref = str(order.get("referenceOrder", ""))
                    emission = str(order.get("emissionDate", ""))
                    billing = order.get("billing") or {}

                    if billing.get("status") == "BILLED":
                        batch_results.append({
                            "order_id": order_id,
                            "reference_order": ref,
                            "emission_date": emission,
                            "proforma_id": billing.get("proformaId"),
                            "status": "ALREADY_BILLED",
                            "reason": "Ya tenía billing.status=BILLED",
                        })
                        continue

                    proforma_id = proforma_map.get(ref)
                    if not proforma_id:
                        batch_results.append({
                            "order_id": order_id,
                            "reference_order": ref,
                            "emission_date": emission,
                            "proforma_id": None,
                            "status": "NOT_IN_LEGACY",
                            "reason": "referenceOrder no encontrado en tabla DCBT",
                        })
                        continue

                    updates_to_apply.append({"_id": order["_id"], "proforma_id": proforma_id})
                    batch_results.append({
                        "order_id": order_id,
                        "reference_order": ref,
                        "emission_date": emission,
                        "proforma_id": proforma_id,
                        "status": "DRY_RUN" if config.DRY_RUN else "UPDATED",
                        "reason": f"proformaId={proforma_id} asignado desde DCBT",
                    })

                # ── Bulk write en MongoDB ─────────────────────────────────
                updated_count, error_count = bulk_update_billing(
                    collection, updates_to_apply, config.DRY_RUN
                )

                # Marcar errores de escritura
                if error_count > 0:
                    for r in batch_results:
                        if r["status"] == "UPDATED":
                            r["status"] = "ERROR"
                            r["reason"] = "Error en bulk_write de MongoDB"

                all_results.extend(batch_results)

                # ── Progreso por lote ─────────────────────────────────────
                b_updated = sum(1 for r in batch_results if r["status"] in ("UPDATED", "DRY_RUN"))
                b_not_legacy = sum(1 for r in batch_results if r["status"] == "NOT_IN_LEGACY")
                b_already = sum(1 for r in batch_results if r["status"] == "ALREADY_BILLED")
                b_errors = sum(1 for r in batch_results if r["status"] == "ERROR")
                print_batch_progress(
                    batch_num, len(batch), len(proforma_map),
                    b_updated, b_not_legacy, b_already, b_errors,
                )

    elapsed = time.time() - start_time
    print_summary(all_results, elapsed)
    save_log(all_results, elapsed)


if __name__ == "__main__":
    main()

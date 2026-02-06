"""
Script orquestador para importación de valores UF a MongoDB.

Flujo:
    1. Descubre los CSVs en uf-reports/ → parsea registros { date, value }
    2. Consulta MongoDB para saber cuáles fechas ya existen
    3. Inserta solo las nuevas (bulk insert)
    4. Genera un log JSON con el resultado

Uso:
    python run_import.py
"""

import json
import os
import sys
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

# Módulos locales del script
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

import config
from services.csv_parser import (
    discover_csv_files,
    parse_csv_file,
)
from repositories.uf_value_repository import (
    COLLECTION_NAME,
    find_existing_dates,
    bulk_insert,
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


def collect_user_input():
    """
    Pide al usuario las opciones clave por terminal.
    Sobreescribe los valores en config con lo que el usuario elija.
    """
    if not sys.stdin.isatty():
        return

    print("\n--- Configuración de ejecución ---\n")

    # 1. ¿Dry run?
    config.DRY_RUN = prompt_yes_no(
        "¿Modo DRY_RUN? (solo muestra lo que haría, sin insertar en DB)",
        config.DRY_RUN,
    )

    if config.DRY_RUN:
        config.DRY_RUN_LIMIT = prompt_int(
            "Cantidad máxima de registros a mostrar (0 = todos)",
            config.DRY_RUN_LIMIT,
            min_val=0,
        )

    print()


# ============================================================================
# FUNCIÓN PRINCIPAL
# ============================================================================

def main():
    # Prompts interactivos
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

    # 1. Descubrir y parsear CSVs
    reports_dir = resolve_path(config.UF_REPORTS_DIR)
    csv_files = discover_csv_files(str(reports_dir))

    if not csv_files:
        print(f"No se encontraron archivos CSV en: {reports_dir}")
        print("  Se esperan archivos con el patrón: UF YYYY.csv")
        return

    print(f"Archivos CSV encontrados en {config.UF_REPORTS_DIR}/:")
    for f in csv_files:
        print(f"  • {f.name}")
    print()

    # Parsear todos los CSVs
    all_documents = []
    csv_stats = {}

    for csv_file in csv_files:
        documents = parse_csv_file(str(csv_file))
        csv_stats[csv_file.name] = len(documents)
        all_documents.extend(documents)
        print(f"  {csv_file.name}: {len(documents)} registros parseados")

    print(f"\n  Total: {len(all_documents)} registros parseados de {len(csv_files)} archivo(s)\n")

    if not all_documents:
        print("No se encontraron registros válidos en los CSVs.")
        return

    # Mostrar configuración
    print_configuration(csv_stats, len(all_documents))

    # Modo DRY_RUN: solo mostrar preview
    if config.DRY_RUN:
        preview_limit = config.DRY_RUN_LIMIT if config.DRY_RUN_LIMIT > 0 else len(all_documents)
        preview = all_documents[:preview_limit]

        print(f"\n[DRY_RUN] Preview de {len(preview)} de {len(all_documents)} registros:\n")

        detail_results = []
        for doc in preview:
            date_display = doc['date'].strftime('%Y-%m-%d')
            date_iso = doc['date'].isoformat()
            print(f"  {date_display}  →  {doc['value']}")
            detail_results.append({
                "date": date_iso,
                "value": doc["value"],
                "status": "DRY_RUN",
                "reason": "Modo simulación, no se insertó en DB",
            })

        print(f"\n[DRY_RUN] No se insertó nada en la base de datos.")
        print(f"  Para ejecutar de verdad, selecciona DRY_RUN = No\n")

        # Guardar log del dry run
        save_log(
            csv_stats=csv_stats,
            total_parsed=len(all_documents),
            already_exist=0,
            inserted=0,
            results=detail_results,
            dry_run=True,
        )
        return

    # 2. Conectar a MongoDB y verificar existentes
    _uri_display = config.MONGO_URI.split("@")[-1] if "@" in config.MONGO_URI else config.MONGO_URI
    print(f"Conectando a MongoDB: ...@{_uri_display} / {config.MONGO_DATABASE}\n")

    with MongoConnection(uri=config.MONGO_URI, database=config.MONGO_DATABASE) as db:
        collection = db[COLLECTION_NAME]

        # 2a. Verificar cuáles ya existen
        all_dates = [doc["date"] for doc in all_documents]
        existing_dates = find_existing_dates(collection, all_dates)

        new_documents = []
        detail_results = []

        for doc in all_documents:
            date_iso = doc["date"].isoformat()
            if date_iso in existing_dates:
                detail_results.append({
                    "date": date_iso,
                    "value": doc["value"],
                    "status": "ALREADY_EXISTS",
                    "reason": "Ya existía en la colección, no se reemplazó",
                })
            else:
                new_documents.append(doc)
                detail_results.append({
                    "date": date_iso,
                    "value": doc["value"],
                    "status": "PENDING_INSERT",
                    "reason": None,
                })

        already_exist_count = sum(1 for r in detail_results if r["status"] == "ALREADY_EXISTS")

        print(f"  Registros ya existentes en DB: {already_exist_count}")
        print(f"  Registros nuevos a insertar:   {len(new_documents)}")
        print()

        if not new_documents:
            print("Todos los registros ya existen en la base de datos. Nada que insertar.")
            save_log(
                csv_stats=csv_stats,
                total_parsed=len(all_documents),
                already_exist=already_exist_count,
                inserted=0,
                results=detail_results,
                dry_run=False,
            )
            return

        # Confirmación antes de insertar
        if sys.stdin.isatty():
            print(f"Se insertarán {len(new_documents)} registros en la colección '{COLLECTION_NAME}'.")
            confirm = prompt_yes_no("¿Confirmar inserción?", True)
            if not confirm:
                print("\nInserción cancelada por el usuario.")
                return
            print()

        # 2b. Bulk insert
        print(f"Insertando {len(new_documents)} registros...")

        try:
            inserted_count = bulk_insert(collection, new_documents)
            print(f"  ✓ {inserted_count} registros insertados correctamente\n")

            # Actualizar estado de los registros insertados
            for entry in detail_results:
                if entry["status"] == "PENDING_INSERT":
                    entry["status"] = "INSERTED"
                    entry["reason"] = "Insertado correctamente en la colección"

        except Exception as e:
            print(f"  ✗ Error durante la inserción: {e}\n")
            inserted_count = 0

            # Marcar todos los pendientes como error
            for entry in detail_results:
                if entry["status"] == "PENDING_INSERT":
                    entry["status"] = "INSERT_ERROR"
                    entry["reason"] = str(e)

    # 3. Resumen y log
    print_summary(
        total_parsed=len(all_documents),
        already_exist=already_exist_count,
        inserted=inserted_count,
    )
    save_log(
        csv_stats=csv_stats,
        total_parsed=len(all_documents),
        already_exist=already_exist_count,
        inserted=inserted_count,
        results=detail_results,
        dry_run=False,
    )


# ============================================================================
# FUNCIONES DE UTILIDAD
# ============================================================================

def resolve_path(relative_path: str) -> Path:
    """Resuelve una ruta relativa al directorio del script."""
    p = Path(relative_path)
    if not p.is_absolute():
        return script_dir / relative_path
    return p


def print_configuration(csv_stats: dict, total_parsed: int):
    print("=" * 60)
    print("=== IMPORTACIÓN DE VALORES UF ===")
    print("=" * 60)
    _uri_safe = "...@" + config.MONGO_URI.split("@")[-1] if "@" in config.MONGO_URI else config.MONGO_URI
    print(f"   • MongoDB URI:   {_uri_safe}")
    print(f"   • Database:      {config.MONGO_DATABASE}")
    print(f"   • Collection:    {COLLECTION_NAME}")
    print(f"   • CSVs:")
    for name, count in csv_stats.items():
        print(f"       - {name}: {count} registros")
    print(f"   • Total parseados: {total_parsed}")
    print(f"   • Dry Run:       {config.DRY_RUN}")
    if config.DRY_RUN:
        limit_label = str(config.DRY_RUN_LIMIT) if config.DRY_RUN_LIMIT > 0 else "sin límite"
        print(f"   • DRY_RUN Limit: {limit_label}")
    print("=" * 60)


def print_summary(total_parsed: int, already_exist: int, inserted: int):
    print()
    print("=" * 50)
    print("=== RESUMEN FINAL ===")
    print(f"   Total parseados del CSV: {total_parsed}")
    print(f"   Ya existían en DB:       {already_exist}")
    print(f"   Insertados nuevos:       {inserted}")
    print("=" * 50)


def save_log(csv_stats: dict, total_parsed: int, already_exist: int,
             inserted: int, results: list, dry_run: bool):
    """
    Guarda un log JSON detallado con el resultado de cada registro.

    Cada entrada en 'results' tiene:
        - date: "2025-01-01"
        - value: 38419.17
        - status: "INSERTED" | "ALREADY_EXISTS" | "INSERT_ERROR" | "DRY_RUN"
        - reason: descripción del resultado
    """
    logs_dir = resolve_path(config.LOGS_DIR)
    logs_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = logs_dir / f"import_{timestamp}.json"

    log_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "database": config.MONGO_DATABASE,
        "collection": COLLECTION_NAME,
        "csv_files": csv_stats,
        "summary": {
            "total_parsed": total_parsed,
            "already_exist": already_exist,
            "inserted": inserted,
            "errors": sum(1 for r in results if r["status"] == "INSERT_ERROR"),
        },
        "results": results,
    }

    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False, default=str)

    print(f"\nLog guardado en: {log_file}")


if __name__ == "__main__":
    main()

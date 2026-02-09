"""
Script orquestador para generación de boletas desde Excel.

Flujo:
    1. Lee Excel de entrada → extrae HESCode
    2. Llama API con requestId → obtiene lista de respuestas
    3. Hace match por HESCode
    4. Genera nuevo Excel con columnas: BOLETA y DETALLE_ERRORES
    5. Genera log JSON con detalle por registro

Uso:
    python run.py
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import List

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
if _env_file.exists() and (not os.environ.get("BOLETAS_API_URL") or not os.environ.get("BOLETAS_REQUEST_ID")):
    with open(_env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                key, val = key.strip(), val.strip().strip('"').strip("'")
                if key and val:
                    os.environ[key] = val

# ── Imports del proyecto ──────────────────────────────────────────────────────

# Módulos locales del script
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

import config
from repositories.boletas_api_client import fetch_boletas_data
from services.excel_processor import (
    read_excel_data,
    create_api_lookup,
    process_records,
    write_output_excel,
    generate_output_filename,
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


def select_input_file() -> str:
    """
    Lista los archivos Excel en reports/ y permite al usuario seleccionar uno.
    Si solo hay uno, lo usa automáticamente.

    Returns:
        Nombre del archivo Excel seleccionado
    """
    reports_dir = resolve_path("./reports")
    excel_files = sorted(reports_dir.glob("*.xlsx"))
    
    # Filtrar archivos temporales de Excel (~$)
    excel_files = [f for f in excel_files if not f.name.startswith("~$")]

    if not excel_files:
        raise FileNotFoundError(f"No se encontraron archivos Excel en {reports_dir}")

    if len(excel_files) == 1:
        # Solo hay uno, usarlo automáticamente
        return excel_files[0].name

    # Múltiples archivos: dejar seleccionar
    print(f"\nArchivos Excel encontrados en reports/:")
    for i, file in enumerate(excel_files, 1):
        print(f"  {i}. {file.name}")
    print()

    while True:
        resp = input(f"Selecciona el número del archivo a procesar [1]: ").strip()
        if not resp:
            return excel_files[0].name
        try:
            idx = int(resp)
            if 1 <= idx <= len(excel_files):
                return excel_files[idx - 1].name
            print(f"  Ingresa un número entre 1 y {len(excel_files)}.")
        except ValueError:
            print("  Ingresa un número válido.")


def collect_user_input():
    """
    Pide al usuario las opciones clave por terminal.
    Sobreescribe los valores en config con lo que el usuario elija.
    """
    if not sys.stdin.isatty():
        return

    print("\n--- Configuración de ejecución ---\n")

    # Seleccionar archivo de entrada
    try:
        config.INPUT_FILE = select_input_file()
    except FileNotFoundError as e:
        print(f"✗ {e}")
        sys.exit(1)

    # ¿Dry run?
    config.DRY_RUN = prompt_yes_no(
        "¿Modo DRY_RUN? (solo muestra preview, no genera Excel de salida)",
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
    if not config.BOLETAS_API_URL:
        raise ValueError(
            "BOLETAS_API_URL no está definida. Agrégala en el archivo .env de la raíz del repo.\n"
            f"  Ruta esperada: {repo_root / '.env'}\n"
            "  Ejemplo: BOLETAS_API_URL=http://localhost:3000"
        )

    if not config.BOLETAS_REQUEST_ID:
        raise ValueError(
            "BOLETAS_REQUEST_ID no está definida. Agrégala en el archivo .env de la raíz del repo.\n"
            f"  Ruta esperada: {repo_root / '.env'}\n"
            "  Ejemplo: BOLETAS_REQUEST_ID=YmF0Y2hfMTc3MDIxMTE2MTQzMl8yODZlODlkMC1mYTU3LTQ1ODctOGY5MS0zOTc5YzAyNGM0MWQ="
        )

    # Mostrar resumen y pedir confirmación
    print_configuration()

    # 1. Leer Excel de entrada
    excel_path = resolve_path(f"./reports/{config.INPUT_FILE}")
    print(f"Leyendo Excel: {excel_path}")

    try:
        wb, excel_records, hes_column = read_excel_data(str(excel_path))
        print(f"  → {len(excel_records)} registros con HESCode encontrados\n")
    except (FileNotFoundError, ValueError) as e:
        print(f"  ✗ Error al leer el Excel: {e}")
        return

    if not excel_records:
        print("No se encontraron registros con HESCode en el Excel.")
        return

    # Aplicar límite en modo DRY_RUN
    total_excel = len(excel_records)
    if config.DRY_RUN and config.DRY_RUN_LIMIT > 0:
        excel_records = excel_records[:config.DRY_RUN_LIMIT]
        print(f"  [DRY_RUN] Limitado a {len(excel_records)} de {total_excel} registros (DRY_RUN_LIMIT={config.DRY_RUN_LIMIT})\n")

    # 2. Consultar API
    print(f"Consultando API: {config.BOLETAS_API_URL}{config.API_ENDPOINT}{config.BOLETAS_REQUEST_ID[:30]}...")

    try:
        api_data = fetch_boletas_data(
            base_url=config.BOLETAS_API_URL,
            request_id=config.BOLETAS_REQUEST_ID,
            endpoint=config.API_ENDPOINT,
        )
        print(f"  → {len(api_data)} documentos recibidos de la API\n")
    except Exception as e:
        print(f"  ✗ Error al consultar la API: {e}")
        return

    # 3. Hacer match y procesar
    print("Procesando registros...")
    api_lookup = create_api_lookup(api_data)
    results = process_records(excel_records, api_lookup)

    # Contar por status
    success_count = sum(1 for r in results if r["status"] == "SUCCESS")
    error_count = sum(1 for r in results if r["status"] == "ERROR")
    not_found_count = sum(1 for r in results if r["status"] == "NOT_FOUND")

    print(f"  ✓ {success_count} exitosos (con BTECode)")
    print(f"  ✗ {error_count} con errores")
    if not_found_count > 0:
        print(f"  ⚠ {not_found_count} no encontrados en API")
    print()

    # Modo DRY_RUN: solo mostrar preview
    if config.DRY_RUN:
        print(f"[DRY_RUN] Preview de {len(results)} registros:\n")
        for result in results[:10]:  # Mostrar máximo 10
            status_symbol = "✓" if result["status"] == "SUCCESS" else "✗"
            print(f"  {status_symbol} HESCode={result['hes_code']} | BOLETA={result['boleta']} | ERROR={result['detalle_errores']}")

        print(f"\n[DRY_RUN] No se generó el Excel de salida.")
        print(f"  Para ejecutar de verdad, selecciona DRY_RUN = No\n")

        # Guardar log del dry run
        save_log(
            total_excel=total_excel,
            total_api=len(api_data),
            results=results,
            output_file=None,
            dry_run=True,
        )
        return

    # 4. Generar Excel de salida
    output_filename = generate_output_filename(config.INPUT_FILE)
    output_path = resolve_path(f"{config.OUTPUT_DIR}/{output_filename}")

    # Confirmación antes de generar
    if sys.stdin.isatty():
        print(f"Se generará el archivo: {output_filename}")
        confirm = prompt_yes_no("¿Confirmar generación?", True)
        if not confirm:
            print("\nGeneración cancelada por el usuario.")
            return
        print()

    print(f"Generando Excel de salida: {output_path}")
    write_output_excel(wb, results, str(output_path))
    print(f"  ✓ Excel generado correctamente\n")

    # 5. Resumen y log
    print_summary(success_count, error_count, not_found_count, total_excel)
    save_log(
        total_excel=total_excel,
        total_api=len(api_data),
        results=results,
        output_file=str(output_path),
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


def print_configuration():
    print("=" * 60)
    print("=== GENERACIÓN DE BOLETAS ===")
    print("=" * 60)
    api_display = config.BOLETAS_API_URL
    request_id_display = config.BOLETAS_REQUEST_ID[:40] + "..." if len(config.BOLETAS_REQUEST_ID) > 40 else config.BOLETAS_REQUEST_ID
    print(f"   • API URL:       {api_display}")
    print(f"   • Request ID:    {request_id_display}")
    print(f"   • Excel entrada: {config.INPUT_FILE}")
    print(f"   • Directorio salida: {config.OUTPUT_DIR}")
    print(f"   • Dry Run:       {config.DRY_RUN}")
    if config.DRY_RUN:
        limit_label = str(config.DRY_RUN_LIMIT) if config.DRY_RUN_LIMIT > 0 else "sin límite"
        print(f"   • DRY_RUN Limit: {limit_label}")
    print("=" * 60)
    print()


def print_summary(success: int, errors: int, not_found: int, total: int):
    print()
    print("=" * 50)
    print("=== RESUMEN FINAL ===")
    print(f"   Total procesados:       {total}")
    print(f"   Exitosos (con boleta):  {success}")
    print(f"   Con errores:            {errors}")
    if not_found > 0:
        print(f"   No encontrados en API:  {not_found}")
    print("=" * 50)


def save_log(total_excel: int, total_api: int, results: List[dict],
             output_file: str, dry_run: bool):
    """
    Guarda un log JSON detallado con el resultado de cada registro.
    """
    logs_dir = resolve_path(config.LOGS_DIR)
    logs_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = logs_dir / f"boletas_{timestamp}.json"

    # Preparar results para el log con toda la info
    log_results = []
    for result in results:
        log_results.append({
            "hes_code": result["hes_code"],
            "boleta": result["boleta"],
            "detalle_errores": result["detalle_errores"],
            "status": result["status"],
        })

    success_count = sum(1 for r in results if r["status"] == "SUCCESS")
    error_count = sum(1 for r in results if r["status"] == "ERROR")
    not_found_count = sum(1 for r in results if r["status"] == "NOT_FOUND")

    log_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "api_url": config.BOLETAS_API_URL,
        "request_id": config.BOLETAS_REQUEST_ID,
        "input_file": config.INPUT_FILE,
        "output_file": output_file,
        "summary": {
            "total_excel_records": total_excel,
            "total_api_documents": total_api,
            "processed": len(results),
            "success": success_count,
            "errors": error_count,
            "not_found": not_found_count,
        },
        "results": log_results,
    }

    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)

    print(f"\nLog guardado en: {log_file}")


if __name__ == "__main__":
    main()

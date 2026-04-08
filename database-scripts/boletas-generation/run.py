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
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional

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
if _env_file.exists() and (
    not os.environ.get("BOLETAS_API_URL") or not os.environ.get("BOLETAS_REQUEST_ID")
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
        print("  Ingresa y o n.")


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
    print("\nArchivos Excel encontrados en reports/:")
    for i, file in enumerate(excel_files, 1):
        print(f"  {i}. {file.name}")
    print()

    while True:
        resp = input("Selecciona el número del archivo a procesar [1]: ").strip()
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


def _validate_config() -> None:
    """Valida variables de entorno requeridas."""
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


def _read_excel_and_limit(excel_path: Path):
    """Lee el Excel y aplica DRY_RUN_LIMIT si corresponde. Returns (wb, excel_records, total_excel)."""
    wb, excel_records, _ = read_excel_data(str(excel_path))
    print(f"  → {len(excel_records)} registros con HESCode encontrados\n")
    total_excel = len(excel_records)
    if config.DRY_RUN and config.DRY_RUN_LIMIT > 0:
        excel_records = excel_records[: config.DRY_RUN_LIMIT]
        print(
            f"  [DRY_RUN] Limitado a {len(excel_records)} de {total_excel} registros (DRY_RUN_LIMIT={config.DRY_RUN_LIMIT})\n"
        )
    return wb, excel_records, total_excel


def _format_elapsed(seconds: float) -> str:
    """Formatea una duración en segundos a formato legible."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    remaining = seconds % 60
    return f"{minutes}m {remaining:.1f}s"


def _get_progress_chunk_size(total_records: int) -> int:
    """
    Determina tamaño de bloque para informar progreso.

    Permite override por variable de entorno BOLETAS_PROGRESS_CHUNK_SIZE.
    """
    env_value = os.getenv("BOLETAS_PROGRESS_CHUNK_SIZE", "").strip()
    if env_value:
        try:
            chunk_size = int(env_value)
            if chunk_size > 0:
                return chunk_size
        except ValueError:
            print(
                "[WARN] BOLETAS_PROGRESS_CHUNK_SIZE inválido. "
                "Se usará configuración automática."
            )

    if total_records <= 200:
        return total_records
    if total_records <= 2_000:
        return 200
    return 500


def _process_records_with_progress(
    excel_records: List[dict], api_lookup: dict
) -> List[dict]:
    """Procesa registros en bloques e imprime progreso para lotes grandes."""
    total_records = len(excel_records)
    if total_records == 0:
        return []

    chunk_size = _get_progress_chunk_size(total_records)
    if chunk_size >= total_records:
        start = time.perf_counter()
        results = process_records(excel_records, api_lookup)
        elapsed = time.perf_counter() - start
        print(f"  → Procesamiento completado en {_format_elapsed(elapsed)}")
        return results

    print(
        "Procesando en bloques "
        f"(total={total_records}, tamaño_bloque={chunk_size})..."
    )
    start_all = time.perf_counter()
    results: List[dict] = []

    for start_idx in range(0, total_records, chunk_size):
        end_idx = min(start_idx + chunk_size, total_records)
        chunk = excel_records[start_idx:end_idx]
        chunk_start = time.perf_counter()
        chunk_results = process_records(chunk, api_lookup)
        chunk_elapsed = time.perf_counter() - chunk_start
        results.extend(chunk_results)

        processed = end_idx
        percent = (processed / total_records) * 100
        total_elapsed = time.perf_counter() - start_all
        avg_per_record = total_elapsed / processed if processed else 0
        remaining_records = total_records - processed
        eta_seconds = avg_per_record * remaining_records
        print(
            f"  • Avance: {processed}/{total_records} ({percent:.1f}%) "
            f"| bloque: {_format_elapsed(chunk_elapsed)} "
            f"| acumulado: {_format_elapsed(total_elapsed)} "
            f"| ETA: {_format_elapsed(eta_seconds)}"
        )

    total_elapsed = time.perf_counter() - start_all
    print(f"  → Procesamiento completado en {_format_elapsed(total_elapsed)}")
    return results


def _fetch_api_data() -> List[dict]:
    """Consulta la API y devuelve la lista de documentos."""
    full_url = (
        f"{config.BOLETAS_API_URL.rstrip('/')}"
        f"{config.API_ENDPOINT}{config.BOLETAS_REQUEST_ID}"
    )
    request_id = config.BOLETAS_REQUEST_ID
    request_tail = request_id[-8:] if len(request_id) >= 8 else request_id
    timeout_seconds = getattr(config, "API_TIMEOUT_SECONDS", 30)
    max_pages = getattr(config, "API_MAX_PAGES", 1000)
    verbose_page_log = getattr(config, "API_VERBOSE_PAGE_LOG", False)

    print("Consultando API de boletas...")
    print(f"  • URL completa: {full_url}")
    print(
        f"  • Request ID: {request_id} "
        f"(largo={len(request_id)}, termina_en={request_tail})"
    )
    print(f"  • Timeout por petición: {timeout_seconds}s")
    print(f"  • Máximo de páginas: {max_pages}")
    print(f"  • Log por página detallado: {verbose_page_log}")

    start = time.perf_counter()
    api_data = fetch_boletas_data(
        base_url=config.BOLETAS_API_URL,
        request_id=config.BOLETAS_REQUEST_ID,
        endpoint=config.API_ENDPOINT,
        timeout=timeout_seconds,
        max_pages=max_pages,
        verbose_page_log=verbose_page_log,
    )
    elapsed = time.perf_counter() - start
    print(
        f"  → {len(api_data)} documentos recibidos de la API en {_format_elapsed(elapsed)}\n"
    )
    return api_data


def _print_results_summary(results: List[dict]) -> None:
    """Imprime resumen de success/error/not_found."""
    success_count = sum(1 for r in results if r["status"] == "SUCCESS")
    error_count = sum(1 for r in results if r["status"] == "ERROR")
    not_found_count = sum(1 for r in results if r["status"] == "NOT_FOUND")
    print(f"  ✓ {success_count} exitosos (con BTECode)")
    print(f"  ✗ {error_count} con errores")
    if not_found_count > 0:
        print(f"  ⚠ {not_found_count} no encontrados en API")
    if error_count > 0:
        error_breakdown = {}
        for result in results:
            if result["status"] != "ERROR":
                continue
            key = result["detalle_errores"] or "SIN_DETALLE"
            error_breakdown[key] = error_breakdown.get(key, 0) + 1
        top_errors = sorted(error_breakdown.items(), key=lambda x: x[1], reverse=True)
        print("  Detalle errores:")
        for error_message, count in top_errors:
            print(f"    - {count}x {error_message}")
    print()


def _run_dry_run(results: List[dict], api_data: List[dict], total_excel: int) -> None:
    """Muestra preview y guarda log en modo DRY_RUN."""
    print(f"[DRY_RUN] Preview de {len(results)} registros:\n")
    for result in results[:10]:
        status_symbol = "✓" if result["status"] == "SUCCESS" else "✗"
        print(
            f"  {status_symbol} HESCode={result['hes_code']} | BOLETA={result['boleta']} | ERROR={result['detalle_errores']}"
        )
    print("\n[DRY_RUN] No se generó el Excel de salida.")
    print("  Para ejecutar de verdad, selecciona DRY_RUN = No\n")
    save_log(
        total_excel=total_excel,
        total_api=len(api_data),
        results=results,
        output_file=None,
        dry_run=True,
    )


def _run_full_generation(
    wb, results: List[dict], api_data: List[dict], total_excel: int
) -> None:
    """Genera Excel de salida, resumen y log (modo no DRY_RUN)."""
    success_count = sum(1 for r in results if r["status"] == "SUCCESS")
    error_count = sum(1 for r in results if r["status"] == "ERROR")
    not_found_count = sum(1 for r in results if r["status"] == "NOT_FOUND")
    output_filename = generate_output_filename(config.INPUT_FILE)
    output_path = resolve_path(f"{config.OUTPUT_DIR}/{output_filename}")
    if sys.stdin.isatty():
        print(f"Se generará el archivo: {output_filename}")
        if not prompt_yes_no("¿Confirmar generación?", True):
            print("\nGeneración cancelada por el usuario.")
            return
        print()
    print(f"Generando Excel de salida: {output_path}")
    write_start = time.perf_counter()
    write_output_excel(wb, results, str(output_path))
    write_elapsed = time.perf_counter() - write_start
    print(f"  ✓ Excel generado correctamente en {_format_elapsed(write_elapsed)}\n")
    print_summary(success_count, error_count, not_found_count, total_excel)
    save_log(
        total_excel=total_excel,
        total_api=len(api_data),
        results=results,
        output_file=str(output_path),
        dry_run=False,
    )


def main():
    collect_user_input()
    job_start = time.perf_counter()
    _validate_config()
    print_configuration()

    excel_path = resolve_path(f"./reports/{config.INPUT_FILE}")
    print(f"Leyendo Excel: {excel_path}")
    try:
        wb, excel_records, total_excel = _read_excel_and_limit(excel_path)
    except (FileNotFoundError, ValueError) as e:
        print(f"  ✗ Error al leer el Excel: {e}")
        return
    if not excel_records:
        print("No se encontraron registros con HESCode en el Excel.")
        return

    try:
        api_data = _fetch_api_data()
    except Exception as e:
        print(f"  ✗ Error al consultar la API: {e}")
        return

    print("Construyendo índice de respuesta API por HESCode...")
    lookup_start = time.perf_counter()
    api_lookup = create_api_lookup(api_data)
    lookup_elapsed = time.perf_counter() - lookup_start
    print(
        f"  → Índice creado con {len(api_lookup)} claves en {_format_elapsed(lookup_elapsed)}\n"
    )

    print("Procesando registros...")
    results = _process_records_with_progress(excel_records, api_lookup)
    _print_results_summary(results)

    if config.DRY_RUN:
        _run_dry_run(results, api_data, total_excel)
        total_elapsed = time.perf_counter() - job_start
        print(f"Tiempo total de ejecución: {_format_elapsed(total_elapsed)}")
        return
    _run_full_generation(wb, results, api_data, total_excel)
    total_elapsed = time.perf_counter() - job_start
    print(f"Tiempo total de ejecución: {_format_elapsed(total_elapsed)}")


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
    request_id_display = config.BOLETAS_REQUEST_ID
    print(f"   • API URL:       {api_display}")
    print(f"   • Request ID:    {request_id_display}")
    print(f"   • Excel entrada: {config.INPUT_FILE}")
    print(f"   • Directorio salida: {config.OUTPUT_DIR}")
    print(f"   • Dry Run:       {config.DRY_RUN}")
    if config.DRY_RUN:
        limit_label = (
            str(config.DRY_RUN_LIMIT) if config.DRY_RUN_LIMIT > 0 else "sin límite"
        )
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


def save_log(
    total_excel: int,
    total_api: int,
    results: List[dict],
    output_file: Optional[str],
    dry_run: bool,
):
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
        log_results.append(
            {
                "hes_code": result["hes_code"],
                "boleta": result["boleta"],
                "detalle_errores": result["detalle_errores"],
                "status": result["status"],
            }
        )

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

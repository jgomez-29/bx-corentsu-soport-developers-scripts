"""
Script orquestador para pruebas de carga HTTP (simulación JMeter).

Endpoint: GET /finmg/app-srv/billing/v1/credit-note-requests/{request_id}/statistics

Flujo:
    1. Lee configuración desde config.py y <ambiente>/config.py
    2. Pide por terminal: ambiente, request_id, cantidad de requests y duración total
    3. Ejecuta los requests GET distribuidos en el tiempo indicado
    4. Muestra progreso en tiempo real
    5. Genera un log JSON con los resultados en logs/

Uso:
    python ./api-tests/bx-app-srv-finmg-billing/credit-note-statistics/run.py
"""

import importlib.util
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ── Resolver directorio del script (para imports locales) ────────────────────
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

# ── Intentar cargar .env desde la raíz del repo ──────────────────────────────
_current = script_dir
while _current != _current.parent:
    _env_candidate = _current / ".env"
    if _env_candidate.exists():
        try:
            from dotenv import load_dotenv

            load_dotenv(str(_env_candidate))
        except ImportError:
            pass
        break
    _current = _current.parent

# ── Imports locales ───────────────────────────────────────────────────────────
import config
from services.http_client import get_request


# ============================================================================
# PROMPTS INTERACTIVOS
# ============================================================================


def prompt_yes_no(message: str, default: bool) -> bool:
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


def prompt_int(message: str, default: int, min_val: int = 1) -> int:
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


def prompt_optional_int(message: str, default: int, min_val: int = 0) -> int:
    while True:
        resp = input(f"{message} [{default}, 0 = sin límite]: ").strip()
        if not resp:
            return default
        try:
            val = int(resp)
            if val >= min_val:
                return val
            print(f"  Debe ser >= {min_val}.")
        except ValueError:
            print("  Ingresa un número entero.")


def prompt_choice(message: str, choices: list, default: str) -> str:
    choices_str = " / ".join(choices)
    while True:
        resp = input(f"{message} ({choices_str}) [{default}]: ").strip().lower()
        if not resp:
            return default
        if resp in choices:
            return resp
        print(f"  Opciones válidas: {choices_str}")


def prompt_string(message: str, default: str) -> str:
    resp = input(f"{message} [{default}]: ").strip()
    return resp if resp else default


def collect_user_input():
    if not sys.stdin.isatty():
        return

    print("\n--- Configuración de prueba de carga ---\n")

    config.ENVIRONMENT = prompt_choice(
        "Ambiente",
        ["dev", "qa"],
        config.ENVIRONMENT,
    )

    config.REQUEST_ID = prompt_string(
        "Request ID del bulk (UUID)",
        config.REQUEST_ID,
    )

    config.TOTAL_REQUESTS = prompt_int(
        "Cantidad de requests a enviar",
        config.TOTAL_REQUESTS,
        min_val=1,
    )

    config.DURATION_SECONDS = prompt_optional_int(
        "Duración total en segundos",
        config.DURATION_SECONDS,
        min_val=0,
    )


# ============================================================================
# UTILIDADES
# ============================================================================


def resolve_path(relative: str) -> Path:
    return (script_dir / relative).resolve()


def load_env_config():
    env = config.ENVIRONMENT
    env_config_file = script_dir / env / "config.py"
    if not env_config_file.exists():
        raise ValueError(
            f"No se encontró la configuración para el ambiente '{env}'.\n"
            f"Archivo esperado: {env_config_file}\n"
            f"Ambientes disponibles: dev, qa"
        )
    spec = importlib.util.spec_from_file_location("env_config", str(env_config_file))
    env_config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(env_config)
    return env_config


# ============================================================================
# MAIN
# ============================================================================


def main():
    collect_user_input()

    env_config = load_env_config()
    full_url = env_config.BASE_URL.rstrip("/") + env_config.ENDPOINT_TEMPLATE.format(
        request_id=config.REQUEST_ID
    )

    total = config.TOTAL_REQUESTS
    duration = config.DURATION_SECONDS
    delay = (duration / total) if (duration > 0 and total > 1) else 0.0

    pad = len(str(total))
    duracion_str = (
        f"{duration}s  →  delay: {delay:.2f}s"
        if duration > 0
        else "sin límite (requests consecutivos)"
    )
    print(f"\n  Ambiente   : {config.ENVIRONMENT}")
    print(f"  URL        : {full_url}")
    print(f"  Requests   : {total}")
    print(f"  Duración   : {duracion_str}\n")

    if sys.stdin.isatty():
        confirm = prompt_yes_no("¿Confirmar ejecución?", default=False)
        if not confirm:
            print("\n  Cancelado.\n")
            return

    results = []
    ok_count = 0
    error_count = 0

    print()
    start_time = time.time()

    for i in range(1, total + 1):
        result = get_request(full_url)
        elapsed_ms = result["elapsed_ms"]
        status_label = "OK   " if result["status"] == "OK" else "ERROR"
        status_code = result.get("status_code") or "---"

        print(f"  [{i:>{pad}}/{total}]  {status_code}  {status_label}  {elapsed_ms} ms")

        results.append(
            {
                "request_num": i,
                "status": result["status"],
                "status_code": result.get("status_code"),
                "elapsed_ms": elapsed_ms,
                "reason": result.get("error") or f"HTTP {result.get('status_code')}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

        if result["status"] == "OK":
            ok_count += 1
        else:
            error_count += 1

        if i < total and delay > 0:
            time.sleep(delay)

    total_elapsed = time.time() - start_time
    avg_ms = int(sum(r["elapsed_ms"] for r in results) / len(results)) if results else 0

    print(f"\n{'─' * 55}")
    print(
        f"  {ok_count} OK  |  {error_count} ERROR"
        f"  |  Promedio: {avg_ms} ms  |  Total: {total_elapsed:.1f}s"
    )

    logs_dir = resolve_path(config.LOGS_DIR)
    logs_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"credit_note_statistics_{timestamp}.json"
    log_path = logs_dir / log_filename

    log_data = {
        "environment": config.ENVIRONMENT,
        "url": full_url,
        "request_id": config.REQUEST_ID,
        "total_requests": total,
        "duration_seconds": duration,
        "summary": {
            "ok": ok_count,
            "error": error_count,
            "avg_elapsed_ms": avg_ms,
            "total_elapsed_seconds": round(total_elapsed, 2),
        },
        "results": results,
    }

    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_data, f, ensure_ascii=False, indent=2)

    print(f"  Log guardado en: logs/{log_filename}\n")


if __name__ == "__main__":
    main()

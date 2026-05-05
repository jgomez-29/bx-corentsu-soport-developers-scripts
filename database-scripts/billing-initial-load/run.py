"""
Punto de entrada para billing-initial-load.

Uso:
    python ./database-scripts/billing-initial-load/run.py
    python ./database-scripts/billing-initial-load/run.py --mode taxDocument
"""

import argparse
import importlib
import os
import sys
from datetime import datetime
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
    load_dotenv(str(_env_file), override=True)
except ImportError:
    pass

if _env_file.exists():
    with open(_env_file, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _, _val = _line.partition("=")
                _key, _val = _key.strip(), _val.strip().strip('"').strip("'")
                if _key and _val:
                    os.environ[_key] = _val

import config

# ── Registro de modos ─────────────────────────────────────────────────────────
# Agregar nuevos modos aquí: "nombre": "modes.nombre_modulo"
MODES = {
    "taxDocument": "modes.tax_document",
    "legacy": "modes.legacy",
}


# ============================================================================
# PROMPTS INTERACTIVOS (compartidos entre modos)
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


def load_accounts_from_file(file_path: str) -> list:
    """
    Lee las cuentas desde un archivo de texto.

    Formato: una cuenta por línea. Líneas con # y vacías se ignoran.

    Raises:
        FileNotFoundError: Si el archivo no existe.
        ValueError: Si el archivo no contiene ninguna cuenta válida.
    """
    path = Path(file_path)
    if not path.is_absolute():
        path = script_dir / file_path

    if not path.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo de cuentas: {path}\n"
            f"  Crea el archivo con una cuenta por línea (# para comentarios)."
        )

    accounts = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                accounts.append(line)

    if not accounts:
        raise ValueError(
            f"El archivo de cuentas no contiene cuentas válidas: {path}\n"
            f"  Agrega al menos una cuenta (una por línea)."
        )

    return accounts


# ============================================================================
# RECOPILACIÓN Y VALIDACIÓN DE INPUTS (compartidos entre modos)
# ============================================================================


def collect_user_input():
    """Recopila fechas, archivo de cuentas y opciones DRY_RUN.
    Si stdin no es interactivo, usa los valores de config.py directamente.
    """
    interactive = sys.stdin.isatty()

    # ── Fechas ────────────────────────────────────────────────────────────────
    has_configured_dates = bool(config.START_DATE and config.END_DATE)

    if has_configured_dates and interactive:
        print(f"  Rango configurado: {config.START_DATE} → {config.END_DATE}")
        if not prompt_yes_no("¿Usar el rango de fechas configurado?", True):
            config.START_DATE = prompt_date("¿Fecha de inicio? (YYYY-MM-DD)", "")
            config.END_DATE = prompt_date("¿Fecha de término? (YYYY-MM-DD)", "")
    else:
        config.START_DATE = prompt_date("¿Fecha de inicio? (YYYY-MM-DD)", config.START_DATE or "")
        config.END_DATE = prompt_date("¿Fecha de término? (YYYY-MM-DD)", config.END_DATE or "")

    # ── Archivo de accounts ───────────────────────────────────────────────────
    if config.ACCOUNTS_FILE and interactive:
        print(f"  Archivo de cuentas configurado: {config.ACCOUNTS_FILE}")
        if not prompt_yes_no("¿Usar el archivo de cuentas configurado?", True):
            config.ACCOUNTS_FILE = input("Ruta al archivo de cuentas: ").strip()
    else:
        display = config.ACCOUNTS_FILE if config.ACCOUNTS_FILE else "accounts/cuentas.txt"
        resp = input(f"Ruta al archivo de cuentas [{display}]: ").strip()
        if resp:
            config.ACCOUNTS_FILE = resp

    config.ACCOUNTS_FILTER = load_accounts_from_file(config.ACCOUNTS_FILE)

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
    """Valida variables de entorno y parámetros requeridos."""
    for var in ("MONGO_URI", "MONGO_DATABASE", "ORACLE_DSN", "ORACLE_USER", "ORACLE_PASSWORD"):
        if not getattr(config, var, None):
            raise ValueError(
                f"{var} no está definida. Agrégala en el archivo .env de la raíz del repo.\n"
                f"  Ruta esperada: {repo_root / '.env'}"
            )
    if not config.ACCOUNTS_FILE:
        raise ValueError(
            "ACCOUNTS_FILE no está definida. Ingresa la ruta al archivo de cuentas.\n"
            f"  Ejemplo: accounts/cuentas.txt (relativo a {script_dir})"
        )
    if not config.ACCOUNTS_FILTER:
        raise ValueError("El archivo de cuentas no contiene cuentas válidas.")
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


# ============================================================================
# SELECCIÓN DE MODO Y DESPACHO
# ============================================================================


def _select_mode_interactive() -> str:
    mode_list = list(MODES.keys())
    print("\n=== billing-initial-load ===\n")
    print("Selecciona el modo de ejecución:")
    for i, name in enumerate(mode_list, 1):
        print(f"  [{i}] {name}")
    print()

    while True:
        resp = input("Modo [1]: ").strip()
        if not resp:
            return mode_list[0]
        if resp in MODES:
            return resp
        try:
            idx = int(resp) - 1
            if 0 <= idx < len(mode_list):
                return mode_list[idx]
        except ValueError:
            pass
        print(f"  Opción inválida. Ingresa un número del 1 al {len(mode_list)} o el nombre del modo.")


def main():
    parser = argparse.ArgumentParser(
        description="billing-initial-load — carga inicial de facturación"
    )
    parser.add_argument(
        "--mode",
        choices=list(MODES.keys()),
        metavar="MODO",
        help=f"Modo de ejecución. Opciones: {', '.join(MODES.keys())}",
    )
    args = parser.parse_args()

    mode_name = args.mode if args.mode else _select_mode_interactive()

    collect_user_input()
    validate_config()

    mode_module = importlib.import_module(MODES[mode_name])
    mode_module.run()


if __name__ == "__main__":
    main()

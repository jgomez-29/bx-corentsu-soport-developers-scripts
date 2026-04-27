"""
Utilidad: extrae datos desde un log de billing-initial-load.

Genera una carpeta con el nombre del log dentro de logs/ y deposita ahí:
  - proforma_series.txt   → proformaSeries únicas, ordenadas
  - sii_folios.txt        → siiFolios únicos, ordenados
  - accounts.txt          → cuentas únicas, ordenadas
  - dcbt_nmr_fac_pf.txt   → números de proforma Oracle únicos, ordenados
  - order_ids.json        → array con todos los orderIds procesados

Uso:
    python ./database-scripts/billing-initial-load/extract_log.py
"""

import json
from pathlib import Path

script_dir = Path(__file__).parent
logs_dir = script_dir / "logs"


def pick_log_file() -> Path:
    """Muestra los logs disponibles y permite seleccionar uno o usar el más reciente."""
    logs = sorted(logs_dir.glob("billing-initial-load_*.json"), reverse=True)
    if not logs:
        raise FileNotFoundError(f"No se encontraron logs en: {logs_dir}")

    print("\n=== extract_log: billing-initial-load ===\n")
    print("Logs disponibles:")
    for i, log in enumerate(logs):
        print(f"  [{i}] {log.name}")

    print(f"\n  [Enter] Usar el más reciente: {logs[0].name}")
    resp = input("\nSelecciona el número del log: ").strip()

    if not resp:
        return logs[0]
    try:
        idx = int(resp)
        if 0 <= idx < len(logs):
            return logs[idx]
        print("Índice fuera de rango, usando el más reciente.")
        return logs[0]
    except ValueError:
        print("Entrada inválida, usando el más reciente.")
        return logs[0]


def extract(log_file: Path):
    print(f"\nLeyendo: {log_file.name} ...")

    with open(log_file, encoding="utf-8") as f:
        data = json.load(f)

    results = data.get("results", [])
    if not results:
        print("El log no contiene resultados.")
        return

    proforma_series = set()
    sii_folios = set()
    accounts = set()
    dcbt_numbers = set()
    order_ids = []

    for entry in results:
        billing = entry.get("billing_applied") or {}

        serie = billing.get("proformaSerie")
        if serie:
            proforma_series.add(str(serie))

        folio = billing.get("siiFolio")
        if folio:
            sii_folios.add(str(folio))

        account = entry.get("account")
        if account:
            accounts.add(str(account))

        dcbt = entry.get("dcbt_nmr_fac_pf")
        if dcbt:
            dcbt_numbers.add(str(dcbt))

        order_id = entry.get("orderId")
        if order_id:
            order_ids.append(str(order_id))

    # Carpeta de salida: logs/<stem del log>/
    out_dir = log_file.parent / log_file.stem
    out_dir.mkdir(exist_ok=True)

    files = {
        "proforma_series.txt": sorted(proforma_series),
        "sii_folios.txt":      sorted(sii_folios),
        "accounts.txt":        sorted(accounts),
        "dcbt_nmr_fac_pf.txt": sorted(dcbt_numbers),
    }

    for filename, values in files.items():
        (out_dir / filename).write_text("\n".join(values), encoding="utf-8")

    (out_dir / "order_ids.json").write_text(
        json.dumps(order_ids, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\n  Carpeta de salida: logs/{log_file.stem}/")
    print(f"  proformaSeries únicas  : {len(proforma_series):>6}  →  proforma_series.txt")
    print(f"  siiFolios únicos       : {len(sii_folios):>6}  →  sii_folios.txt")
    print(f"  Cuentas únicas         : {len(accounts):>6}  →  accounts.txt")
    print(f"  DCBT NMR FAC PF únicos : {len(dcbt_numbers):>6}  →  dcbt_nmr_fac_pf.txt")
    print(f"  OrderIds               : {len(order_ids):>6}  →  order_ids.json")
    print()


def main():
    log_file = pick_log_file()
    extract(log_file)


if __name__ == "__main__":
    main()

"""
Servicio para leer y parsear los CSVs de valores UF.

Archivos esperados: uf-reports/UF YYYY.csv

Formato del CSV:
    Separador: ; (punto y coma)
    Encoding: UTF-8
    Cabecera: Día;Ene;Feb;Mar;Abr;May;Jun;Jul;Ago;Sep;Oct;Nov;Dic
    Valores: "39.703,50" (punto = miles, coma = decimal)
    Celdas vacías: sin valor para esa fecha → se ignoran

Año:
    Se extrae del nombre del archivo: "UF 2025.csv" → 2025
"""

import csv
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from entities.uf_value import build_uf_document


# Mapeo de nombres de mes en español → número de mes
MONTH_MAP = {
    "Ene": 1, "Feb": 2, "Mar": 3, "Abr": 4,
    "May": 5, "Jun": 6, "Jul": 7, "Ago": 8,
    "Sep": 9, "Oct": 10, "Nov": 11, "Dic": 12,
}


def parse_uf_value(raw: str) -> Optional[float]:
    """
    Convierte un valor UF del formato CSV al float real.
    "39.703,50" → 39703.50
    "" → None

    Args:
        raw: Valor como string del CSV

    Returns:
        Float o None si está vacío o no es parseable
    """
    raw = raw.strip()
    if not raw:
        return None

    try:
        # Quitar puntos de miles, reemplazar coma decimal por punto
        cleaned = raw.replace(".", "").replace(",", ".")
        return float(cleaned)
    except ValueError:
        return None


def extract_year_from_filename(filename: str) -> Optional[int]:
    """
    Extrae el año del nombre del archivo.
    "UF 2025.csv" → 2025

    Args:
        filename: Nombre del archivo

    Returns:
        Año como entero o None si no se puede extraer
    """
    match = re.search(r"(\d{4})", filename)
    if match:
        return int(match.group(1))
    return None


def parse_csv_file(csv_path: str) -> List[Dict[str, Any]]:
    """
    Lee un CSV de valores UF y genera la lista de documentos para insertar.

    Args:
        csv_path: Ruta al archivo CSV

    Returns:
        Lista de documentos { date: datetime, value: float }
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo CSV: {csv_path}")

    year = extract_year_from_filename(path.name)
    if not year:
        raise ValueError(f"No se pudo extraer el año del nombre del archivo: {path.name}")

    documents = []

    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")

        for row in reader:
            day_str = row.get("Día", "").strip()
            if not day_str:
                continue

            try:
                day = int(day_str)
            except ValueError:
                continue

            # Recorrer cada mes
            for month_name, month_number in MONTH_MAP.items():
                raw_value = row.get(month_name, "")
                value = parse_uf_value(raw_value)

                if value is None:
                    continue

                # Validar que la fecha sea válida (ej: 31 de Feb no existe)
                try:
                    doc = build_uf_document(year, month_number, day, value)
                    documents.append(doc)
                except ValueError:
                    # Fecha inválida (ej: 30 de Feb), se ignora
                    continue

    return documents


def discover_csv_files(reports_dir: str) -> List[Path]:
    """
    Busca todos los archivos CSV de UF en el directorio de reportes.

    Args:
        reports_dir: Ruta al directorio de reportes

    Returns:
        Lista de paths a archivos CSV, ordenados por nombre
    """
    path = Path(reports_dir)
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el directorio de reportes: {reports_dir}")

    csv_files = sorted(path.glob("UF *.csv"))
    return csv_files


def parse_all_csv_files(reports_dir: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Lee todos los CSVs de UF en el directorio y retorna los documentos agrupados por archivo.

    Args:
        reports_dir: Ruta al directorio de reportes

    Returns:
        Diccionario { nombre_archivo: [documentos] }
    """
    csv_files = discover_csv_files(reports_dir)
    results = {}

    for csv_file in csv_files:
        documents = parse_csv_file(str(csv_file))
        results[csv_file.name] = documents

    return results

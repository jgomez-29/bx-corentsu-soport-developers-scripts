"""
Módulo para construir mensajes de proformas para SQS

IMPORTANTE: Los proformaSeries deben existir en la base de datos.
Este módulo solo carga proformaSeries reales desde archivo o lista.
"""

from typing import List, Dict, Any
import json


def load_proformas(
    input_file: str = None,
    proforma_series_list: List[str] = None,
    default_account: str = None
) -> List[Dict[str, Any]]:
    """
    Carga proformas desde archivo o lista
    
    IMPORTANTE: Los proformaSeries deben existir en la base de datos.
    Este método solo carga los proformaSeries especificados, no los genera.
    
    Si usas proforma_series_list: ["SERIE-123", "SERIE-456"] → carga esas series
    Si usas input_file: carga desde archivo JSON
    
    Args:
        input_file: Ruta al archivo JSON con proformas
        proforma_series_list: Lista directa de proformaSeries
        default_account: Account por defecto (si es None, se omite)
    
    Returns:
        Lista de diccionarios con proformaSerie (y account si se especifica)
    """
    # Opción 1: Lista directa de proformaSeries
    if proforma_series_list:
        proformas = []
        for serie in proforma_series_list:
            proforma = {
                "proformaSerie": serie,
            }
            
            # Agregar account solo si se especifica
            if default_account:
                proforma["account"] = default_account
            
            proformas.append(proforma)
        
        return proformas
    
    # Opción 2: Archivo JSON
    if input_file:
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            raise ValueError(f"{input_file} debe contener un array JSON")
        
        proformas = []
        for item in data:
            # Si es un string, es solo el proformaSerie
            if isinstance(item, str):
                proforma = {
                    "proformaSerie": item,
                }
                
                # Agregar account solo si se especifica
                if default_account:
                    proforma["account"] = default_account
                
                proformas.append(proforma)
            
            # Si es un dict, extraer campos
            elif isinstance(item, dict):
                proforma_serie = item.get("proformaSerie")
                if not proforma_serie:
                    continue  # Saltar si no tiene proformaSerie
                
                proforma = {
                    "proformaSerie": proforma_serie,
                }
                
                # Agregar account del item o del default
                account = item.get("account", default_account)
                if account:
                    proforma["account"] = account
                
                proformas.append(proforma)
        
        return proformas
    
    raise ValueError("Debes especificar INPUT_FILE o PROFORMA_SERIES_LIST")

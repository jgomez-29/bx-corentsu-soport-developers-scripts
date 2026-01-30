"""
Módulo para construir mensajes de órdenes para SQS
"""

from datetime import datetime, timezone
from typing import List, Dict, Any
import json


def generate_orders_for_create(
    base: str,
    start: int,
    count: int,
    order_type: int
) -> List[Dict[str, Any]]:
    """
    Genera órdenes para modo CREATE con orderIds incrementales
    
    Ejemplo: base="TEST", start=1, count=3
    Genera: TEST-000001, TEST-000002, TEST-000003
    """
    orders = []
    for i in range(count):
        order_id = f"{base}-{start + i:06d}"
        orders.append({
            "orderId": order_id,
            "orderType": order_type,
        })
    return orders


def load_orders_for_modify(
    input_file: str = None,
    order_ids_list: List[str] = None,
    default_order_type: int = 3
) -> List[Dict[str, Any]]:
    """
    Carga órdenes para modo MODIFY
    
    Si usas order_ids_list: ["123", "456"] → genera órdenes con esos IDs
    Si usas input_file: carga desde archivo JSON
    """
    # Generar modifierDate una sola vez
    modifier_date = datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
    
    # Opción 1: Lista directa de orderIds
    if order_ids_list:
        return [
            {
                "orderId": oid,
                "orderType": default_order_type,
                "modifierDate": modifier_date
            }
            for oid in order_ids_list
        ]
    
    # Opción 2: Archivo JSON
    if input_file:
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            raise ValueError(f"{input_file} debe contener un array JSON")
        
        orders = []
        for item in data:
            # Si es un string, es solo el orderId
            if isinstance(item, str):
                orders.append({
                    "orderId": item,
                    "orderType": default_order_type,
                    "modifierDate": modifier_date
                })
            # Si es un dict, extraer campos
            elif isinstance(item, dict):
                order_id = item.get("orderId")
                if not order_id:
                    continue  # Saltar si no tiene orderId
                
                orders.append({
                    "orderId": order_id,
                    "orderType": item.get("orderType", default_order_type),
                    "modifierDate": item.get("modifierDate", modifier_date)
                })
        
        return orders
    
    raise ValueError("Debes especificar INPUT_FILE o ORDER_IDS_LIST")

"""
Módulo para construir mensajes de SaleTransmission para SQS

Este módulo carga SaleTransmission desde archivo JSON o genera mensajes
para pruebas de estrés del CreateSaleTransmissionUseCase.
"""

from typing import List, Dict, Any
import json


def load_sale_transmissions(
    input_file: str = None,
    sale_transmissions_list: List[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Carga SaleTransmission desde archivo o lista
    
    IMPORTANTE: Los campos mínimos requeridos son:
    - society (String)
    - type (String: "order", "invoice" o "proforma")
    - siiFolio (String)
    - docType (Integer)
    - account (String)
    - costDetail (CostDetail)
    - prepaidEmission (PrepaidEmission) - OBLIGATORIO solo si type="order"
      Para type="proforma" o type="invoice", NO se requiere prepaidEmission
    
    Nota: El campo discount en costDetail es opcional.
    
    Los siguientes campos se calculan automáticamente y NO deben enviarse:
    - docClass, docTypeDescription, dummy, status, cenco, paymentKey,
      createdAt, updatedAt
    
    Args:
        input_file: Ruta al archivo JSON con SaleTransmission
        sale_transmissions_list: Lista directa de objetos SaleTransmission
    
    Returns:
        Lista de diccionarios con SaleTransmission
    """
    # Opción 1: Lista directa de SaleTransmission
    if sale_transmissions_list:
        return sale_transmissions_list
    
    # Opción 2: Archivo JSON
    if input_file:
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            raise ValueError(f"{input_file} debe contener un array JSON")
        
        return data
    
    raise ValueError("Debes especificar INPUT_FILE o SALE_TRANSMISSIONS_LIST")


def generate_sale_transmissions_for_stress_test(
    base_sii_folio: str,
    start: int,
    count: int,
    template: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Genera múltiples SaleTransmission para pruebas de estrés
    
    Args:
        base_sii_folio: Base para generar siiFolio incrementales
        start: Número inicial del contador
        count: Cantidad total de mensajes a generar
        template: Plantilla base de SaleTransmission
    
    Returns:
        Lista de SaleTransmission generados
    """
    sale_transmissions = []
    
    for i in range(count):
        sale_transmission = template.copy()
        sale_transmission["siiFolio"] = f"{base_sii_folio}-{start + i:06d}"
        
        # Si tiene prepaidEmission, también actualizar orderId
        if sale_transmission.get("prepaidEmission"):
            prepaid = sale_transmission["prepaidEmission"].copy()
            if "orderId" in prepaid:
                prepaid["orderId"] = f"ORD-{start + i:06d}"
            sale_transmission["prepaidEmission"] = prepaid
        
        sale_transmissions.append(sale_transmission)
    
    return sale_transmissions

"""
Builders de documentos MongoDB para billing-initial-load.

Colecciones afectadas:
  - orders:           actualización del subdocumento billing (build_billing)
  - proformas:        creación de proforma legacy (build_proforma)
  - proformaRequests: trazabilidad de proforma (build_proforma_request)
  - invoices:         creación de invoice (build_invoice)

Estructura del documento invoice.details (siempre 2 entradas):
  [
    { net: 0, quantity: 1, total: 0, gloss: "TRANSPORTE DE CARGA CTA CTE: {account}" },
    { net: serviceCharges.total, quantity: 1, total: serviceCharges.total, gloss: "VALOR FLETE" }
  ]
  Cuando no hay proforma disponible, el segundo detalle usa net=0 y total=0.
"""

import uuid
from datetime import datetime, timezone


def generate_part1(company_name: str) -> str:
    """
    Genera el segmento part1 (4 caracteres) de la proformaSerie.

    Algoritmo:
      Por cada ronda, avanza el char_index e itera todos los tokens acumulando
      un carácter por token. Se detiene al alcanzar 4 caracteres. Si los tokens
      se agotan antes, rellena repitiendo el último carácter.

    Ejemplos:
      "BLUEX"                  → "BLUE"  (token único: B, L, U, E)
      "Blue Express"           → "BELX"  (ronda 0: B,E → ronda 1: l,x)
      "Blue Express Logística" → "BELL"  (ronda 0: B,E,L → ronda 1: l)
      "AB"                     → "ABBB"  (agotado en ronda 1, rellena con B)
      "" / None                → "XXXX"
    """
    if not company_name or not company_name.strip():
        return "XXXX"

    tokens = company_name.strip().split()
    result = ""
    char_index = 0

    while len(result) < 4:
        added = False
        for token in tokens:
            if char_index < len(token) and len(result) < 4:
                result += token[char_index].upper()
                added = True
        if not added:
            break
        char_index += 1

    while len(result) < 4:
        result += result[-1]

    return result[:4]


def generate_proforma_serie(part1: str, created_at_iso: str, dcbt_nmr_fac_pf: str) -> str:
    """
    Genera la proformaSerie completa.

    Formato: PRO_{part1}_{YYYYMM}_{dcbt_nmr_fac_pf}
    Ejemplo: PRO_BELX_202604_12345
    """
    if created_at_iso and len(created_at_iso) >= 7:
        year_month = created_at_iso[:4] + created_at_iso[5:7]
    else:
        year_month = "000000"
    return f"PRO_{part1}_{year_month}_{dcbt_nmr_fac_pf}"


def _to_iso_str(value) -> str | None:
    """Convierte datetime a ISO string; si ya es string lo retorna tal cual."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _to_datetime(value) -> datetime | None:
    """Convierte ISO string o datetime a datetime con timezone UTC para almacenar como Date en MongoDB."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def build_billing_legacy(order: dict, proforma_doc: dict | None) -> dict:
    """
    Construye el dict de billing para el modo legacy.

    En el modo legacy no hay taxDocument en la orden; la factura proviene de Oracle.
    Por eso no se incluyen siiFolio, billingDate ni detail (se añadirán cuando
    se implemente la lógica de invoices del modo legacy).

    Campos siempre presentes: status.
    Campos condicionales (solo si proforma_doc): proformaId, proformaSerie.

    Args:
        order:        Documento de la OS desde MongoDB.
        proforma_doc: Documento de proforma resuelto (o None si no hay).
    """
    billing = {
        "status": "BILLED",
    }

    if proforma_doc:
        billing["proformaId"] = proforma_doc.get("_id_hex")
        billing["proformaSerie"] = proforma_doc.get("proformaSerie")

    return billing


def build_billing(order: dict, proforma_doc: dict | None, oser_data: dict) -> dict:
    """
    Construye el dict de billing para actualizar orders.billing.

    Campos siempre presentes: siiFolio, status, billingDate, detail.
    Campos condicionales (solo si proforma_doc): proformaId, proformaSerie.

    Args:
        order:        Documento de la OS desde MongoDB.
        proforma_doc: Documento de proforma resuelto (o None si no hay).
        oser_data:    Dict con 'retries' y 'additional_charges' de Oracle OSER.
    """
    tax_doc = order.get("taxDocument") or {}

    billing = {
        "siiFolio": tax_doc.get("siiDocumentId"),
        "status": "BILLED",
        "billingDate": tax_doc.get("createDate"),
        "detail": {
            "retries": int(oser_data.get("retries") or 0),
            "additionalCharges": int(oser_data.get("additional_charges") or 0),
        },
    }

    if proforma_doc:
        billing["proformaId"] = proforma_doc.get("_id_hex")
        billing["proformaSerie"] = proforma_doc.get("proformaSerie")

    return billing


def build_proforma(proforma_data: dict, account: str, sii_folio: str, dcbt_nmr_fac_pf: str) -> dict:
    """
    Construye el documento para insertar en la colección proformas.

    Colección: proformas
    Campos clave: account, status="BILLED", isLegacyProforma=True,
                  proformaSerie (generada con dcbt_nmr_fac_pf), serviceCharges,
                  orderTypeCounters, companyName, requestId (UUID).

    Args:
        proforma_data:    Dict con datos de Oracle (find_proforma_data).
        account:          Cuenta del vendedor (order.seller.account).
        sii_folio:        Folio SII (taxDocument.siiDocumentId).
        dcbt_nmr_fac_pf:  Número de proforma del legado (usado en proformaSerie).
    """
    company_name = proforma_data.get("company_name") or ""
    # Fallback: DCBT_FCH_CREACION → MAX(DCBT_FCH_ULD_MOD) → fecha actual
    created_at_iso = (
        proforma_data.get("created_at")
        or proforma_data.get("updated_at")
        or datetime.now(timezone.utc).isoformat()
    )
    updated_at_iso = proforma_data.get("updated_at") or created_at_iso

    flete = int(proforma_data.get("valor_flete") or 0)
    garantia = int(proforma_data.get("garantia_extendida") or 0)
    reintentos = int(proforma_data.get("reintentos") or 0)
    monobulto = int(proforma_data.get("monobulto") or 0)
    padres = int(proforma_data.get("padres") or 0)
    hijas = int(proforma_data.get("hijas") or 0)

    part1 = generate_part1(company_name)
    proforma_serie = generate_proforma_serie(part1, created_at_iso, str(dcbt_nmr_fac_pf))

    return {
        "account": account,
        "status": "BILLED",
        "isDirectBilling": True,
        "isLegacyProforma": True,
        "proformaSerie": proforma_serie,
        "orderCount": monobulto + padres + hijas,
        "orderTypeCounters": {
            "multiOrderParentCounter": padres,
            "multiOrderChildCounter": hijas,
            "multiPackageOrderCounter": 0,
            "singleOrderCounter": monobulto,
        },
        "freightZeroCounter": 0,
        "serviceCharges": {
            "freight": flete,
            "extendedWarranty": garantia,
            "retries": reintentos,
            "total": flete + garantia + reintentos,
        },
        "companyName": company_name,
        "siiFolio": sii_folio,
        "createdAt": _to_datetime(created_at_iso),
        "updatedAt": _to_datetime(updated_at_iso),
        "publishedAt": _to_datetime(updated_at_iso),
        "closingGroupCodes": [],
        "requestId": str(uuid.uuid4()),
        "createdBy": None,
        "updatedBy": None,
    }


def build_proforma_request(proforma_doc: dict, order_id: str) -> dict:
    """
    Construye el documento para insertar en la colección proformaRequests.

    Colección: proformaRequests
    Asociado a la proforma vía requestId (UUID compartido).
    createdBy = "billing-initial-load" (distinto del consumer Java).
    """
    from datetime import timezone
    now = datetime.now(timezone.utc)
    order_count = proforma_doc.get("orderCount") or 0

    return {
        "requestId": proforma_doc.get("requestId"),
        "filters": {"orderId": order_id},
        "type": "LEGACY",
        "createdBy": "billing-initial-load",
        "createdAt": now,
        "updatedAt": now,
        "elementsToProcess": order_count,
        "elementsSentToProcess": order_count,
        "elementsProcessed": order_count,
        "elementsProcessedSuccessfully": order_count,
        "elementsProcessedWithErrors": 0,
    }


def build_invoice_legacy(
    sii_folio: str,
    sii_document_path: str | None,
    account: str,
    proforma_doc: dict | None,
) -> dict:
    """
    Construye el documento para insertar en la colección invoices (modo legacy).

    A diferencia de build_invoice(), no depende de taxDocument. Los datos de
    identificación de la factura provienen de Oracle (OAPV/DEMV).

    Colección: invoices
    type: "12" (Factura Electrónica — fijo para el modo legacy)
    receiver: None (pendiente de implementación futura)

    Args:
        sii_folio:         Folio SII (OAPV_VALOR de Oracle).
        sii_document_path: Ruta del documento SII (DEMV_RUTA_WEB de Oracle).
        account:           Cuenta del vendedor.
        proforma_doc:      Documento de proforma resuelto (o None si no hay).
    """
    service_charges_total = 0
    document_date = None

    if proforma_doc:
        service_charges_total = (proforma_doc.get("serviceCharges") or {}).get("total", 0)
        document_date = _to_datetime(proforma_doc.get("createdAt"))

    if proforma_doc:
        related_elements = [
            {"identifier": proforma_doc.get("proformaSerie", ""), "type": "proforma_serie"}
        ]
    else:
        related_elements = []

    tax_rate = 19
    tax_amount = round(service_charges_total * tax_rate / 100)
    total = service_charges_total + tax_amount

    return {
        "siiFolio": sii_folio,
        "type": "12",
        "typeDesc": "FACTURA ELECTRONICA",
        "siiDocumentPath": sii_document_path,
        "society": "1700",
        "account": account,
        "documentDate": document_date,
        "realDate": document_date,
        "receiver": None,
        "relatedElements": related_elements,
        "totalDetail": {
            "exemptSubtotal": 0,
            "taxableSubTotal": service_charges_total,
            "discount": 0,
            "taxRate": tax_rate,
            "cashAdjustment": 0,
            "tax": tax_amount,
            "total": total,
            "totalToPay": total,
        },
        "details": [
            {
                "net": 0,
                "quantity": 1,
                "total": 0,
                "gloss": f"TRANSPORTE DE CARGA CTA CTE: {account}",
            },
            {
                "net": service_charges_total,
                "quantity": 1,
                "total": service_charges_total,
                "gloss": "VALOR FLETE",
            },
        ],
        "isLegacy": True,
    }
    """
    Construye el documento para insertar en la colección invoices.

    Colección: invoices
    relatedElements: proforma_serie si hay proforma, order si no.
    totalDetail: calculado con serviceCharges.total de la proforma (IVA 19%).
    details: siempre 2 entradas (TRANSPORTE DE CARGA + VALOR FLETE).

    Args:
        order:        Documento de la OS desde MongoDB.
        proforma_doc: Documento de proforma resuelto (o None si no hay).
    """
    tax_doc = order.get("taxDocument") or {}
    account = (order.get("seller") or {}).get("account", "")

    service_charges_total = 0
    if proforma_doc:
        service_charges_total = (proforma_doc.get("serviceCharges") or {}).get("total", 0)

    if proforma_doc:
        related_elements = [
            {"identifier": proforma_doc.get("proformaSerie", ""), "type": "proforma_serie"}
        ]
    else:
        related_elements = [
            {"identifier": order.get("orderId", ""), "type": "order"}
        ]

    date_iso = _to_iso_str(tax_doc.get("createDate"))

    tax_rate = 19
    tax_amount = round(service_charges_total * tax_rate / 100)
    total = service_charges_total + tax_amount

    return {
        "siiFolio": tax_doc.get("siiDocumentId"),
        "type": tax_doc.get("type"),
        "typeDesc": tax_doc.get("typeDesc"),
        "siiDocumentPath": tax_doc.get("path"),
        "society": "1700",
        "account": account,
        "documentDate": date_iso,
        "realDate": date_iso,
        "receiver": tax_doc.get("receiver"),
        "relatedElements": related_elements,
        "totalDetail": {
            "exemptSubtotal": 0,
            "taxableSubTotal": service_charges_total,
            "discount": 0,
            "taxRate": tax_rate,
            "cashAdjustment": 0,
            "tax": tax_amount,
            "total": total,
            "totalToPay": total,
        },
        "details": [
            {
                "net": 0,
                "quantity": 1,
                "total": 0,
                "gloss": f"TRANSPORTE DE CARGA CTA CTE: {account}",
            },
            {
                "net": service_charges_total,
                "quantity": 1,
                "total": service_charges_total,
                "gloss": "VALOR FLETE",
            },
        ],
        "isLegacy": True,
    }

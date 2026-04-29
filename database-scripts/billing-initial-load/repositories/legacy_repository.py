"""
Repositorio de consultas al legado Oracle para billing-initial-load.

Tablas Oracle:
  - DCBT:  número de proforma (DCBT_NMR_FAC_PF) por EEVV_NMR_ID
  - OSER:  costos de OS (retries, additionalCharges) por EEVV_NMR_ID
  - CLHL:  datos de empresa (CLHL_NMBR_JURIDICO)

Todas las consultas batch usan bind variables dinámicas (:1, :2, ...) para
evitar SQL injection y respetar el límite de 1000 items por cláusula IN.
"""

import decimal
from datetime import datetime

import query_logger


def _to_int(value) -> int:
    """Convierte Decimal/None/float a int de forma segura."""
    if value is None:
        return 0
    if isinstance(value, decimal.Decimal):
        return int(value)
    return int(value)


def _to_iso_str(value) -> str | None:
    """Convierte datetime de Oracle a ISO string; None si nulo."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def batch_find_dcbt(cursor, reference_orders: list) -> dict:
    """
    Consulta DCBT_NMR_FAC_PF y DCBT_NMR_FAC_REAL para un lote de EEVV_NMR_ID.

    Máx. 1000 items por llamada (límite Oracle IN clause).
    Retorna: {eevv_nmr_id: {"dcbt_nmr_fac_pf": str, "dcbt_nmr_fac_real": str|None}}.
    """
    if not reference_orders:
        return {}

    placeholders = ", ".join([f":{i + 1}" for i in range(len(reference_orders))])
    sql = (
        f"SELECT EEVV_NMR_ID, DCBT_NMR_FAC_PF, DCBT_NMR_FAC_REAL "
        f"FROM DCBT "
        f"WHERE EEVV_NMR_ID IN ({placeholders})"
    )
    query_logger.log_oracle(sql, reference_orders)
    cursor.execute(sql, reference_orders)
    result = {}
    for row in cursor.fetchall():
        eevv_id = str(row[0]) if row[0] is not None else None
        dcbt_nmr = str(row[1]) if row[1] is not None else None
        if eevv_id and dcbt_nmr:
            result[eevv_id] = {
                "dcbt_nmr_fac_pf": dcbt_nmr,
                "dcbt_nmr_fac_real": str(row[2]) if row[2] is not None else None,
            }
    return result


def batch_find_oser(cursor, reference_orders: list) -> dict:
    """
    Consulta costos OSER para un lote de EEVV_NMR_ID.

    Máx. 1000 items por llamada.
    Retorna: {eevv_nmr_id: {"retries": int, "additional_charges": int}}.
    """
    if not reference_orders:
        return {}

    placeholders = ", ".join([f":{i + 1}" for i in range(len(reference_orders))])
    sql = (
        f"SELECT "
        f"    EEVV_NMR_ID, "
        f"    (NVL(oser_vlor_gasto_carrier_pp, 0) + NVL(oser_vlor_gasto_carrier_cc, 0)) AS retries, "
        f"    (NVL(oser_vlor_varios_pp, 0) + NVL(oser_vlor_varios_cc, 0)) AS additional_charges "
        f"FROM OSER "
        f"WHERE EEVV_NMR_ID IN ({placeholders})"
    )
    query_logger.log_oracle(sql, reference_orders)
    cursor.execute(sql, reference_orders)
    result = {}
    for row in cursor.fetchall():
        eevv_id = str(row[0]) if row[0] is not None else None
        if eevv_id:
            result[eevv_id] = {
                "retries": _to_int(row[1]),
                "additional_charges": _to_int(row[2]),
            }
    return result


def batch_find_proforma_data_bulk(cursor, facturas: list) -> dict:
    """
    Consulta los datos de proforma para un lote de DCBT_NMR_FAC_PF.

    Agrupa por DCBT_NMR_FAC_PF y CLHL_NMBR_JURIDICO para obtener resultados
    individuales por cada factura.

    Máx. 1000 items por llamada.
    Retorna: {dcbt_nmr_fac_pf: dict} con los mismos campos que find_proforma_data.
    """
    if not facturas:
        return {}

    placeholders = ", ".join([f":{i + 1}" for i in range(len(facturas))])
    sql = f"""
        SELECT
            DCBT_NMR_FAC_PF,
            SUM(CASE OSER.OSER_TIPO_MULTIOS WHEN 0 THEN 1 ELSE 0 END) AS monobulto,
            SUM(CASE OSER.OSER_TIPO_MULTIOS WHEN 1 THEN 1 ELSE 0 END) AS padres,
            SUM(CASE OSER.OSER_TIPO_MULTIOS WHEN 2 THEN 1 ELSE 0 END) AS hijas,
            CLHL_NMBR_JURIDICO                                         AS company_name,
            SUM(OSER.OSER_VLOR_FLETE_PP)                               AS valor_flete,
            SUM(OSER.OSER_VLOR_SEGURO)                                 AS garantia_extendida,
            SUM(OSER.OSER_VLOR_GASTO_CARRIER_PP)                       AS reintentos,
            MIN(DCBT_FCH_CREACION)                                     AS created_at,
            MAX(DCBT_FCH_ULD_MOD)                                      AS updated_at,
            MAX(DCBT_NMR_FAC_REAL)                                     AS dcbt_nmr_fac_real
        FROM DCBT
        INNER JOIN OSER ON OSER.EEVV_NMR_ID = DCBT.EEVV_NMR_ID
        INNER JOIN CLHL ON OSER.CLHL_CDG_EMBA = CLHL.CLHL_CDG
                       AND OSER.CLHL_SCRS_EMBA = CLHL.CLHL_SCRS
        WHERE DCBT_NMR_FAC_PF IN ({placeholders})
        GROUP BY DCBT_NMR_FAC_PF, CLHL_NMBR_JURIDICO
    """
    query_logger.log_oracle(sql, facturas)
    cursor.execute(sql, facturas)
    result = {}
    for row in cursor.fetchall():
        dcbt_nmr = str(row[0]) if row[0] is not None else None
        if dcbt_nmr:
            result[dcbt_nmr] = {
                "monobulto": _to_int(row[1]),
                "padres": _to_int(row[2]),
                "hijas": _to_int(row[3]),
                "company_name": str(row[4]) if row[4] is not None else "",
                "valor_flete": _to_int(row[5]),
                "garantia_extendida": _to_int(row[6]),
                "reintentos": _to_int(row[7]),
                "created_at": _to_iso_str(row[8]),
                "updated_at": _to_iso_str(row[9]),
                "dcbt_nmr_fac_real": str(row[10]) if row[10] is not None else None,
            }
    return result


def batch_find_order_series(cursor, facturas: list) -> dict:
    """
    Retorna el mapeo orderId → DCBT_NMR_FAC_PF para un lote de facturas.

    Hace JOIN entre DCBT y EEVV para obtener EEVV_NMR_SERIE (= orderId en MongoDB).
    Permite actualizar masivamente todas las órdenes asociadas a las facturas del lote,
    incluyendo órdenes que no formaban parte del batch de MongoDB original.

    Máx. 1000 items por llamada.
    Retorna: {eevv_nmr_serie (orderId): dcbt_nmr_fac_pf}
    """
    if not facturas:
        return {}

    placeholders = ", ".join([f":{i + 1}" for i in range(len(facturas))])
    sql = (
        f"SELECT EEVV.EEVV_NMR_SERIE, DCBT.DCBT_NMR_FAC_PF "
        f"FROM DCBT "
        f"INNER JOIN EEVV ON EEVV.EEVV_NMR_ID = DCBT.EEVV_NMR_ID "
        f"WHERE DCBT.DCBT_NMR_FAC_PF IN ({placeholders})"
    )
    query_logger.log_oracle(sql, facturas)
    cursor.execute(sql, facturas)
    result = {}
    for row in cursor.fetchall():
        serie = str(row[0]) if row[0] is not None else None
        dcbt_nmr = str(row[1]) if row[1] is not None else None
        if serie and dcbt_nmr:
            result[serie] = dcbt_nmr
    return result


def find_proforma_data(cursor, dcbt_nmr_fac_pf: str) -> dict | None:
    """
    Consulta los datos completos de una proforma desde el legado.

    Hace JOIN entre DCBT, OSER y CLHL para obtener montos y nombre empresa.
    Retorna: dict con monobulto, padres, hijas, company_name, valor_flete,
             garantia_extendida, reintentos, created_at (ISO str), updated_at (ISO str).
    Retorna None si no se encuentran datos.
    """
    sql = """
        SELECT
            SUM(CASE OSER.OSER_TIPO_MULTIOS WHEN 0 THEN 1 ELSE 0 END) AS monobulto,
            SUM(CASE OSER.OSER_TIPO_MULTIOS WHEN 1 THEN 1 ELSE 0 END) AS padres,
            SUM(CASE OSER.OSER_TIPO_MULTIOS WHEN 2 THEN 1 ELSE 0 END) AS hijas,
            CLHL_NMBR_JURIDICO                                         AS company_name,
            SUM(OSER.OSER_VLOR_FLETE_PP)                               AS valor_flete,
            SUM(OSER.OSER_VLOR_SEGURO)                                 AS garantia_extendida,
            SUM(OSER.OSER_VLOR_GASTO_CARRIER_PP)                       AS reintentos,
            MIN(DCBT_FCH_CREACION)                                     AS created_at,
            MAX(DCBT_FCH_ULD_MOD)                                      AS updated_at
        FROM DCBT
        INNER JOIN OSER ON OSER.EEVV_NMR_ID = DCBT.EEVV_NMR_ID
        INNER JOIN CLHL ON OSER.CLHL_CDG_EMBA = CLHL.CLHL_CDG
                       AND OSER.CLHL_SCRS_EMBA = CLHL.CLHL_SCRS
        WHERE DCBT_NMR_FAC_PF = :1
        GROUP BY CLHL_NMBR_JURIDICO
    """
    query_logger.log_oracle(sql, [dcbt_nmr_fac_pf])
    cursor.execute(sql, [dcbt_nmr_fac_pf])
    row = cursor.fetchone()
    if row is None:
        return None

    return {
        "monobulto": _to_int(row[0]),
        "padres": _to_int(row[1]),
        "hijas": _to_int(row[2]),
        "company_name": str(row[3]) if row[3] is not None else "",
        "valor_flete": _to_int(row[4]),
        "garantia_extendida": _to_int(row[5]),
        "reintentos": _to_int(row[6]),
        "created_at": _to_iso_str(row[7]),
        "updated_at": _to_iso_str(row[8]),
    }


def batch_find_invoice_data(cursor, dcbt_nmr_fac_reals: list) -> dict:
    """
    Consulta siiFolio (OAPV_VALOR) y siiDocumentPath (DEMV_RUTA_WEB) para
    un lote de DCBT_NMR_FAC_REAL.

    La tabla OAPV almacena atributos clave-valor por OS; el código 'FOLIO_SII'
    corresponde al folio SII de la factura. DEMV contiene la ruta del documento.

    Máx. 1000 items por llamada (límite Oracle IN clause).
    Retorna: {dcbt_nmr_fac_real: {"sii_folio": str, "sii_document_path": str|None}}
    """
    if not dcbt_nmr_fac_reals:
        return {}

    placeholders = ", ".join([f":{i + 1}" for i in range(len(dcbt_nmr_fac_reals))])
    sql = (
        f"SELECT OAPV.EEVV_NMR_ID, OAPV_VALOR, DEMV_RUTA_WEB "
        f"FROM OAPV "
        f"JOIN DEMV ON OAPV.EEVV_NMR_ID = DEMV.EEVV_NMR_ID "
        f"WHERE OAPV.EEVV_NMR_ID IN ({placeholders}) "
        f"AND OAPV.OAPC_CDG = 'FOLIO_SII'"
    )
    query_logger.log_oracle(sql, dcbt_nmr_fac_reals)
    cursor.execute(sql, dcbt_nmr_fac_reals)
    result = {}
    for row in cursor.fetchall():
        eevv_id = str(row[0]) if row[0] is not None else None
        if eevv_id:
            result[eevv_id] = {
                "sii_folio": str(row[1]) if row[1] is not None else None,
                "sii_document_path": str(row[2]) if row[2] is not None else None,
            }
    return result

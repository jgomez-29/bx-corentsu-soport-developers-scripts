"""
Servicio de billing para el modo legacy de billing-initial-load.

A diferencia de billing_service.py (modo taxDocument), este servicio no depende
del campo taxDocument de la orden. La fuente de verdad para las facturas es Oracle.

Flujo por lote:
  1. Separar OS ya facturadas (skip) de candidatas.
  2. Consultar Oracle: DCBT_NMR_FAC_PF + DCBT_NMR_FAC_REAL por referenceOrder (batch_find_dcbt).
     La lista DISTINCT de facturas se deriva de los valores del mapa resultante.
  3. Cargar proformas MongoDB por accounts del lote → map (account, dcbt_nmr) → proforma.
  4. Detectar facturas sin proforma existente.
  5. Consultar Oracle batch: datos de proforma para las faltantes.
  6. Crear proformas faltantes en MongoDB.
  6b. Recopilar DCBT_NMR_FAC_REAL del batch.
  6c. Consultar Oracle OAPV/DEMV: siiFolio + siiDocumentPath por DCBT_NMR_FAC_REAL.
  6d. Pre-calcular siiFolios del batch (regla: proforma existente con siiFolio → usarlo; si no, Oracle).
  6e. Verificar en MongoDB qué invoices ya existen (filtrando por siiFolio + type='12').
  7. Consultar Oracle: EEVV_NMR_SERIE → DCBT_NMR_FAC_PF para TODAS las facturas del lote.
     Esto puede actualizar más órdenes que las del batch original.
  8. Construir billing + invoice legacy para cada orden con su proforma.
  9. bulk_write masivo sobre orders + insert_many invoices.

Statuses de resultado:
  - UPDATED:                  Billing actualizado con proforma asociada.
  - UPDATED_WITHOUT_PROFORMA: Billing actualizado pero sin proforma (orden sin factura en Oracle).
  - SKIPPED_ALREADY_BILLED:   OS ya tenía billing.status = BILLED.
  - DRY_RUN:                  Simulación, sin escrituras.
  - ERROR:                    Error al procesar la OS.
"""

from repositories import (
    legacy_repository,
    order_repository,
    proforma_repository,
    proforma_request_repository,
    invoice_repository,
)
from entities import order as entities


def _make_skip_result(order: dict, status: str, reason: str) -> dict:
    emission_date = order.get("emissionDate")
    if hasattr(emission_date, "isoformat"):
        emission_date = emission_date.isoformat()
    return {
        "orderId": order.get("orderId", ""),
        "referenceOrder": order.get("referenceOrder", ""),
        "emissionDate": emission_date,
        "account": (order.get("seller") or {}).get("account", ""),
        "dcbt_nmr_fac_pf": None,
        "proforma_action": "SKIPPED",
        "invoice_action": "SKIPPED",
        "billing_applied": None,
        "status": status,
        "reason": reason,
    }


def _chunks(lst: list, size: int):
    """Divide una lista en sublistas de hasta `size` elementos (límite Oracle IN)."""
    for i in range(0, len(lst), size):
        yield lst[i: i + size]


def process_batch(batch: list, mongo_db, oracle_conn, dry_run: bool) -> list:
    """
    Procesa un lote de órdenes en modo legacy y aplica la lógica de billing.

    Args:
        batch:       Lista de documentos de orders desde MongoDB.
        mongo_db:    Base de datos pymongo (db object).
        oracle_conn: Conexión Oracle activa (oracledb.Connection).
        dry_run:     Si True, simula sin escribir en MongoDB.

    Returns:
        Lista de result dicts con el detalle de cada OS procesada.
    """
    results = []
    candidates = []

    # ── Paso 1: separar skips de candidatas ──────────────────────────────────
    for order in batch:
        billing_status = (order.get("billing") or {}).get("status")
        if billing_status == "BILLED":
            results.append(_make_skip_result(order, "SKIPPED_ALREADY_BILLED", "OS ya facturada"))
            continue
        candidates.append(order)

    if not candidates:
        return results

    # ── Paso 2: obtener referenceOrders válidos del lote ─────────────────────
    reference_orders = [o.get("referenceOrder", "") for o in candidates]
    valid_refs = [r for r in reference_orders if r]

    # ── Paso 3: cargar proformas MongoDB por accounts del lote ────────────────
    proformas_col = mongo_db[proforma_repository.COLLECTION_NAME]
    proforma_requests_col = mongo_db[proforma_request_repository.COLLECTION_NAME]
    orders_col = mongo_db[order_repository.COLLECTION_NAME]
    invoices_col = mongo_db[invoice_repository.COLLECTION_NAME]

    unique_accounts = list({
        (o.get("seller") or {}).get("account", "")
        for o in candidates
        if (o.get("seller") or {}).get("account")
    })

    existing_proformas = proforma_repository.find_by_accounts(proformas_col, unique_accounts)
    proforma_map = {}
    for p in existing_proformas:
        p["_id_hex"] = str(p["_id"])
        serie = p.get("proformaSerie") or ""
        if "_" in serie:
            numeric_id = serie.rsplit("_", 1)[-1]
            proforma_map[(p.get("account", ""), numeric_id)] = p

    # ── Paso 4: detectar facturas sin proforma existente ─────────────────────
    # Consulta Oracle: DCBT_NMR_FAC_PF + DCBT_NMR_FAC_REAL por referenceOrder.
    # Su resultado también sirve para derivar all_facturas (DISTINCT DCBT_NMR_FAC_PF),
    # eliminando la necesidad de batch_find_dcbt_distinct como query separada.
    ref_to_dcbt = {}  # {ref: {"dcbt_nmr_fac_pf": str, "dcbt_nmr_fac_real": str|None}}
    if valid_refs:
        with oracle_conn.cursor() as cursor:
            for chunk in _chunks(valid_refs, 1000):
                ref_to_dcbt.update(legacy_repository.batch_find_dcbt(cursor, chunk))

    # all_facturas: DISTINCT DCBT_NMR_FAC_PF derivado del paso anterior (evita query extra a Oracle)
    all_facturas = list({
        data["dcbt_nmr_fac_pf"]
        for data in ref_to_dcbt.values()
        if data.get("dcbt_nmr_fac_pf")
    })

    ref_to_account = {
        o.get("referenceOrder", ""): (o.get("seller") or {}).get("account", "")
        for o in candidates
    }

    missing_facturas = set()
    for ref, dcbt_data in ref_to_dcbt.items():
        dcbt_nmr = dcbt_data["dcbt_nmr_fac_pf"]
        account = ref_to_account.get(ref, "")
        if account and (account, dcbt_nmr) not in proforma_map:
            missing_facturas.add(dcbt_nmr)

    # ── Paso 5: consultar Oracle batch para proformas faltantes ──────────────
    proforma_data_map = {}
    if missing_facturas:
        missing_list = list(missing_facturas)
        with oracle_conn.cursor() as cursor:
            for chunk in _chunks(missing_list, 1000):
                proforma_data_map.update(
                    legacy_repository.batch_find_proforma_data_bulk(cursor, chunk)
                )

    # ── Paso 6: crear proformas faltantes en MongoDB ──────────────────────────
    # Para crear la proforma necesitamos el account, que obtenemos a través del
    # mapa ref → account → dcbt_nmr.
    dcbt_to_account = {}
    for ref, dcbt_data in ref_to_dcbt.items():
        dcbt_nmr = dcbt_data["dcbt_nmr_fac_pf"]
        account = ref_to_account.get(ref, "")
        if account and dcbt_nmr:
            dcbt_to_account[dcbt_nmr] = account

    created_dcbt_nmrs = set()  # facturas cuya proforma fue creada en este batch

    # Acumular todas las proformas nuevas para hacer insert_many en un solo round-trip
    new_proformas_to_insert = []   # lista de (dcbt_nmr, account, proforma_doc)

    for dcbt_nmr, pf_data in proforma_data_map.items():
        account = dcbt_to_account.get(dcbt_nmr, "")
        if not account:
            continue
        if (account, dcbt_nmr) in proforma_map:
            continue

        new_proforma = entities.build_proforma(pf_data, account, "", dcbt_nmr)
        new_proformas_to_insert.append((dcbt_nmr, account, new_proforma))

    if new_proformas_to_insert:
        if not dry_run:
            proforma_docs_only = [pf for _, _, pf in new_proformas_to_insert]
            inserted_ids = proforma_repository.save_many(proformas_col, proforma_docs_only)
            for i, (dcbt_nmr, account, new_proforma) in enumerate(new_proformas_to_insert):
                new_proforma["_id_hex"] = inserted_ids[i]

            proforma_requests = [
                entities.build_proforma_request(pf, "")
                for _, _, pf in new_proformas_to_insert
            ]
            proforma_request_repository.save_many(proforma_requests_col, proforma_requests)
        else:
            for _, _, new_proforma in new_proformas_to_insert:
                new_proforma["_id_hex"] = "dry_run_id"

        for dcbt_nmr, account, new_proforma in new_proformas_to_insert:
            proforma_map[(account, dcbt_nmr)] = new_proforma
            created_dcbt_nmrs.add(dcbt_nmr)

    # ── Paso 6b: recopilar todos los DCBT_NMR_FAC_REAL del batch ─────────────
    all_dcbt_nmr_reals = list({
        dcbt_data["dcbt_nmr_fac_real"]
        for dcbt_data in ref_to_dcbt.values()
        if dcbt_data.get("dcbt_nmr_fac_real")
    })

    # ── Paso 6c: consultar Oracle: siiFolio + siiDocumentPath ────────────────
    invoice_data_map = {}  # {dcbt_nmr_fac_real: {"sii_folio": str, "sii_document_path": str|None}}
    if all_dcbt_nmr_reals:
        with oracle_conn.cursor() as cursor:
            for chunk in _chunks(all_dcbt_nmr_reals, 1000):
                invoice_data_map.update(
                    legacy_repository.batch_find_invoice_data(cursor, chunk)
                )

    # ── Paso 6d: pre-calcular siiFolios del batch para chequeo de existencia ──
    # Regla:
    #   - Si la proforma EXISTÍA (FOUND) y tiene siiFolio → usar proforma.siiFolio
    #   - En cualquier otro caso (proforma CREATED o sin siiFolio) → usar Oracle
    all_sii_folios_in_batch = set()
    for order in candidates:
        ref = order.get("referenceOrder", "")
        account = (order.get("seller") or {}).get("account", "")
        dcbt_data = ref_to_dcbt.get(ref, {})
        dcbt_nmr = dcbt_data.get("dcbt_nmr_fac_pf") if dcbt_data else None
        dcbt_nmr_real = dcbt_data.get("dcbt_nmr_fac_real") if dcbt_data else None

        proforma_doc_pre = proforma_map.get((account, dcbt_nmr)) if dcbt_nmr else None
        if proforma_doc_pre and dcbt_nmr not in created_dcbt_nmrs and proforma_doc_pre.get("siiFolio"):
            sii_folio_pre = proforma_doc_pre["siiFolio"]
        else:
            oracle_inv = invoice_data_map.get(dcbt_nmr_real, {}) if dcbt_nmr_real else {}
            sii_folio_pre = oracle_inv.get("sii_folio")

        if sii_folio_pre:
            all_sii_folios_in_batch.add(sii_folio_pre)

    # ── Paso 6e: verificar invoices existentes en MongoDB ────────────────────
    existing_folios = invoice_repository.find_existing_sii_folios(
        invoices_col, list(all_sii_folios_in_batch), invoice_type="12"
    )

    # ── Paso 7: mapeo orderId → dcbt_nmr para TODAS las facturas del lote ─────
    # Este paso puede recuperar más órdenes que las del batch original
    # (todas las órdenes Oracle asociadas a esas facturas).
    order_series_map = {}  # {orderId: dcbt_nmr}
    if all_facturas:
        with oracle_conn.cursor() as cursor:
            for chunk in _chunks(all_facturas, 1000):
                order_series_map.update(
                    legacy_repository.batch_find_order_series(cursor, chunk)
                )

    # Mapa plano dcbt_nmr → proforma_doc para las órdenes extra (paso 7).
    # En ese caso no tenemos el account de la orden, pero sí sabemos que la
    # proforma existe en proforma_map porque fue creada o encontrada en este batch.
    # Cada dcbt_nmr identifica unívocamente a una proforma.
    dcbt_to_proforma_doc = {}
    for (_, dcbt_nmr_key), proforma_doc_val in proforma_map.items():
        dcbt_to_proforma_doc[dcbt_nmr_key] = proforma_doc_val

    # ── Paso 8: construir billing + invoice y acumular updates masivos ───────
    billing_updates = []
    invoices_to_create = []

    # Procesar las órdenes del batch original
    for order in candidates:
        order_id = order.get("orderId", "")
        ref_order = order.get("referenceOrder", "")
        account = (order.get("seller") or {}).get("account", "")
        emission_date = order.get("emissionDate")
        if hasattr(emission_date, "isoformat"):
            emission_date = emission_date.isoformat()

        dcbt_data = ref_to_dcbt.get(ref_order)
        dcbt_nmr = dcbt_data["dcbt_nmr_fac_pf"] if dcbt_data else None
        dcbt_nmr_real = dcbt_data["dcbt_nmr_fac_real"] if dcbt_data else None
        proforma_doc = None
        proforma_action = "SKIPPED"

        if dcbt_nmr:
            proforma_doc = proforma_map.get((account, dcbt_nmr))
            if proforma_doc:
                proforma_action = "CREATED" if dcbt_nmr in created_dcbt_nmrs else "FOUND"
            else:
                proforma_action = "NOT_FOUND"

        billing_doc = entities.build_billing_legacy(order, proforma_doc)

        if not dry_run:
            billing_updates.append({"orderId": order_id, "billing": billing_doc})

        # ── Invoice ──────────────────────────────────────────────────────────
        # Resolver siiFolio: usar el de la proforma si existía y lo tiene;
        # si no, usar el resultado de Oracle.
        oracle_inv_data = invoice_data_map.get(dcbt_nmr_real, {}) if dcbt_nmr_real else {}
        if proforma_doc and proforma_action == "FOUND" and proforma_doc.get("siiFolio"):
            sii_folio_for_inv = proforma_doc["siiFolio"]
        else:
            sii_folio_for_inv = oracle_inv_data.get("sii_folio")
        sii_document_path = oracle_inv_data.get("sii_document_path")

        invoice_action = "SKIPPED"
        invoice_created_doc = None
        if sii_folio_for_inv and sii_folio_for_inv not in existing_folios:
            invoice_doc = entities.build_invoice_legacy(
                sii_folio_for_inv, sii_document_path, account, proforma_doc
            )
            invoices_to_create.append(invoice_doc)
            existing_folios.add(sii_folio_for_inv)
            invoice_action = "CREATED"
            invoice_created_doc = invoice_doc
        elif sii_folio_for_inv:
            invoice_action = "FOUND"

        if dry_run:
            status_val = "DRY_RUN"
            reason = "Modo DRY_RUN activo"
        elif proforma_doc:
            status_val = "UPDATED"
            reason = "Billing actualizado con proforma"
        else:
            status_val = "UPDATED_WITHOUT_PROFORMA"
            reason = "Sin DCBT_NMR_FAC_PF en Oracle o sin proforma disponible"

        result = {
            "orderId": order_id,
            "referenceOrder": ref_order,
            "emissionDate": emission_date,
            "account": account,
            "dcbt_nmr_fac_pf": dcbt_nmr,
            "dcbt_nmr_fac_real": dcbt_nmr_real,
            "proforma_action": proforma_action,
            "invoice_action": invoice_action,
            "billing_applied": billing_doc,
            "status": status_val,
            "reason": reason,
        }

        if proforma_action == "CREATED":
            result["proforma_created"] = {k: v for k, v in proforma_doc.items() if k != "_id"}
        if invoice_action == "CREATED":
            result["invoice_created"] = invoice_created_doc

        results.append(result)

    # Procesar órdenes adicionales descubiertas en paso 7 (no estaban en el batch)
    batch_order_ids = {o.get("orderId", "") for o in candidates}
    extra_updates = []
    for order_id, dcbt_nmr in order_series_map.items():
        if order_id in batch_order_ids:
            continue  # ya procesada arriba

        # Para órdenes extra no tenemos el account directamente.
        # Usamos el mapa plano dcbt_nmr → proforma_doc para garantizar que
        # siempre se guarden proformaId y proformaSerie cuando existe la proforma.
        proforma_doc = dcbt_to_proforma_doc.get(dcbt_nmr)
        billing_doc = entities.build_billing_legacy({}, proforma_doc)

        if not dry_run:
            extra_updates.append({"orderId": order_id, "billing": billing_doc})

    # ── Paso 9: escrituras masivas en MongoDB ─────────────────────────────────
    write_stats = {"orders_matched": 0, "orders_modified": 0}
    if not dry_run:
        all_updates = billing_updates + extra_updates
        if all_updates:
            mongo_result = order_repository.bulk_write_billing(orders_col, all_updates)
            write_stats["orders_matched"] = mongo_result["matched"]
            write_stats["orders_modified"] = mongo_result["modified"]
        if invoices_to_create:
            invoice_repository.save_many(invoices_col, invoices_to_create)

    return results, write_stats

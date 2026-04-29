"""
Servicio de billing para billing-initial-load.

Orquesta la lógica de consolidación para un lote de órdenes de servicio:
  1. Separa OS candidatas de las que se deben skipear (ya BILLED o sin taxDocument).
  2. Consulta Oracle en lote: DCBT (número de proforma) y OSER (costos).
  3. Resuelve proformas: busca en MongoDB por accounts, crea las faltantes.
  4. Verifica invoices existentes por siiFolio.
  5. Construye billing + invoice por cada OS candidata.
  6. Escribe en MongoDB: bulk_write billing + insert_many invoices (si no dry_run).

Escenarios manejados:
  - Escenario 1: OS con DCBT_NMR_FAC_PF y sin proforma en MongoDB → crea proforma
  - Escenario 2: OS con DCBT_NMR_FAC_PF y proforma ya en MongoDB → reutiliza proforma
  - Escenario 3: OS sin DCBT_NMR_FAC_PF → billing sin proformaId/proformaSerie
  - Escenario 4: OS con billing.status = "BILLED" → skip
  - Escenario 5: OS sin taxDocument → skip

Referencia Java: ConsolidationOrderUseCase.java (handleBilling, handleProforma, handleInvoice)
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


def process_batch(batch: list, mongo_db, oracle_conn, dry_run: bool) -> list:
    """
    Procesa un lote de órdenes y aplica la lógica de billing.

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
        if not order.get("taxDocument"):
            results.append(_make_skip_result(order, "SKIPPED_NO_TAX_DOCUMENT", "Sin taxDocument"))
            continue
        candidates.append(order)

    if not candidates:
        return results

    # ── Paso 2: consultas Oracle en lote ─────────────────────────────────────
    reference_orders = [o.get("referenceOrder", "") for o in candidates]
    valid_refs = [r for r in reference_orders if r]

    with oracle_conn.cursor() as cursor:
        dcbt_map = legacy_repository.batch_find_dcbt(cursor, valid_refs)
        oser_map = legacy_repository.batch_find_oser(cursor, valid_refs)

    # ── Paso 3: lookup masivo de proformas en MongoDB por accounts (R-07) ────
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
        p["_id_hex"] = str(p["_id"])  # normalizar para que build_billing siempre use _id_hex
        serie = p.get("proformaSerie") or ""
        if "_" in serie:
            numeric_id = serie.rsplit("_", 1)[-1]
            proforma_map[(p.get("account", ""), numeric_id)] = p

    # ── Paso 4: detectar proformas faltantes y consultarlas al legado ────────
    missing_dcbt_ids = set()
    for order in candidates:
        ref = order.get("referenceOrder", "")
        dcbt_nmr = dcbt_map.get(ref)
        account = (order.get("seller") or {}).get("account", "")
        if dcbt_nmr and (account, str(dcbt_nmr)) not in proforma_map:
            missing_dcbt_ids.add(str(dcbt_nmr))

    proforma_data_map = {}
    if missing_dcbt_ids:
        with oracle_conn.cursor() as cursor:
            for dcbt_nmr in missing_dcbt_ids:
                pf_data = legacy_repository.find_proforma_data(cursor, dcbt_nmr)
                if pf_data:
                    proforma_data_map[dcbt_nmr] = pf_data

    # ── Paso 5: verificar invoices existentes ────────────────────────────────
    sii_folios_in_batch = [
        (o.get("taxDocument") or {}).get("siiDocumentId", "")
        for o in candidates
    ]
    existing_folios = invoice_repository.find_existing_sii_folios(
        invoices_col, [f for f in sii_folios_in_batch if f]
    )

    # ── Paso 6: construir billing + invoice por cada candidata ───────────────
    billing_updates = []
    invoices_to_create = []

    for order in candidates:
        order_id = order.get("orderId", "")
        ref_order = order.get("referenceOrder", "")
        account = (order.get("seller") or {}).get("account", "")
        tax_doc = order.get("taxDocument") or {}
        sii_folio = tax_doc.get("siiDocumentId", "")

        dcbt_nmr = dcbt_map.get(ref_order)
        oser_data = oser_map.get(ref_order, {})

        proforma_doc = None
        proforma_action = "SKIPPED"

        if dcbt_nmr:
            dcbt_str = str(dcbt_nmr)
            proforma_doc = proforma_map.get((account, dcbt_str))

            if proforma_doc:
                proforma_action = "FOUND"
            elif dcbt_str in proforma_data_map:
                # Crear nueva proforma
                new_proforma = entities.build_proforma(
                    proforma_data_map[dcbt_str], account, sii_folio, dcbt_str
                )
                if not dry_run:
                    new_id_hex = proforma_repository.save(proformas_col, new_proforma)
                    new_proforma["_id_hex"] = new_id_hex
                    pr = entities.build_proforma_request(new_proforma, order_id)
                    proforma_request_repository.save(proforma_requests_col, pr)
                else:
                    new_proforma["_id_hex"] = "dry_run_id"

                proforma_doc = new_proforma
                proforma_action = "CREATED"
                proforma_map[(account, dcbt_str)] = proforma_doc

        billing_doc = entities.build_billing(order, proforma_doc, oser_data)

        if not dry_run:
            billing_updates.append({"orderId": order_id, "billing": billing_doc})

        # Invoice
        invoice_action = "FOUND"
        invoice_created_doc = None
        if sii_folio and sii_folio not in existing_folios:
            invoice_doc = entities.build_invoice(order, proforma_doc)
            invoices_to_create.append(invoice_doc)
            existing_folios.add(sii_folio)
            invoice_action = "CREATED"
            invoice_created_doc = invoice_doc

        emission_date = order.get("emissionDate")
        if hasattr(emission_date, "isoformat"):
            emission_date = emission_date.isoformat()

        if dry_run:
            status_val = "DRY_RUN"
            reason = "Modo DRY_RUN activo"
        elif proforma_doc:
            status_val = "UPDATED"
            reason = "Billing actualizado con proforma"
        else:
            status_val = "UPDATED_WITHOUT_PROFORMA"
            reason = "Billing actualizado sin proforma (DCBT no disponible en legado)"

        result = {
            "orderId": order_id,
            "referenceOrder": ref_order,
            "emissionDate": emission_date,
            "account": account,
            "dcbt_nmr_fac_pf": dcbt_nmr,
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

    # ── Paso 7: escrituras masivas en MongoDB ────────────────────────────────
    write_stats = {"orders_matched": 0, "orders_modified": 0}
    if not dry_run:
        if billing_updates:
            mongo_result = order_repository.bulk_write_billing(orders_col, billing_updates)
            write_stats["orders_matched"] = mongo_result["matched"]
            write_stats["orders_modified"] = mongo_result["modified"]
        if invoices_to_create:
            invoice_repository.save_many(invoices_col, invoices_to_create)

    return results, write_stats

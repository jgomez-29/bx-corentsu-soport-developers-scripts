"""
Servicio de billing para el modo legacy de billing-initial-load.

A diferencia de billing_service.py (modo taxDocument), este servicio no depende
del campo taxDocument de la orden. La fuente de verdad para las facturas es Oracle.

Flujo por lote:
  1. Separar OS ya facturadas (skip) de candidatas.
  2. Consultar Oracle: DISTINCT DCBT_NMR_FAC_PF para los referenceOrders del lote.
  3. Cargar proformas MongoDB por accounts del lote → map (account, dcbt_nmr) → proforma.
  4. Detectar facturas sin proforma existente.
  5. Consultar Oracle batch: datos de proforma para las faltantes.
  6. Crear proformas faltantes en MongoDB.
  7. Consultar Oracle: EEVV_NMR_SERIE → DCBT_NMR_FAC_PF para TODAS las facturas del lote.
     Esto puede actualizar más órdenes que las del batch original.
  8. Construir billing legacy para cada orden con su proforma.
  9. bulk_write masivo sobre orders.

Statuses de resultado:
  - UPDATED:               Billing actualizado con proforma asociada.
  - UPDATED_WITHOUT_PROFORMA: Billing actualizado pero sin proforma (orden sin factura en Oracle).
  - SKIPPED_ALREADY_BILLED: OS ya tenía billing.status = BILLED.
  - DRY_RUN:               Simulación, sin escrituras.
  - ERROR:                 Error al procesar la OS.
"""

from repositories import (
    legacy_repository,
    order_repository,
    proforma_repository,
    proforma_request_repository,
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

    # ── Paso 2: obtener DISTINCT DCBT_NMR_FAC_PF para los referenceOrders ────
    reference_orders = [o.get("referenceOrder", "") for o in candidates]
    valid_refs = [r for r in reference_orders if r]

    all_facturas = []
    if valid_refs:
        with oracle_conn.cursor() as cursor:
            # Respetar límite de 1000 items en Oracle IN clause
            for chunk in _chunks(valid_refs, 1000):
                all_facturas.extend(legacy_repository.batch_find_dcbt_distinct(cursor, chunk))
    all_facturas = list(set(all_facturas))  # deduplicar entre chunks

    # ── Paso 3: cargar proformas MongoDB por accounts del lote ────────────────
    proformas_col = mongo_db[proforma_repository.COLLECTION_NAME]
    proforma_requests_col = mongo_db[proforma_request_repository.COLLECTION_NAME]
    orders_col = mongo_db[order_repository.COLLECTION_NAME]

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
    # Necesitamos saber qué account corresponde a cada factura.
    # Construimos el mapa ref → (dcbt_nmr, account) desde las órdenes del batch.
    # Nota: usamos batch_find_dcbt (retorna {ref: dcbt_nmr}) para el mapping individual.
    ref_to_dcbt = {}
    if valid_refs:
        with oracle_conn.cursor() as cursor:
            for chunk in _chunks(valid_refs, 1000):
                ref_to_dcbt.update(legacy_repository.batch_find_dcbt(cursor, chunk))

    ref_to_account = {
        o.get("referenceOrder", ""): (o.get("seller") or {}).get("account", "")
        for o in candidates
    }

    missing_facturas = set()
    for ref, dcbt_nmr in ref_to_dcbt.items():
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
    for ref, dcbt_nmr in ref_to_dcbt.items():
        account = ref_to_account.get(ref, "")
        if account and dcbt_nmr:
            dcbt_to_account[dcbt_nmr] = account

    created_dcbt_nmrs = set()  # facturas cuya proforma fue creada en este batch

    for dcbt_nmr, pf_data in proforma_data_map.items():
        account = dcbt_to_account.get(dcbt_nmr, "")
        if not account:
            continue
        if (account, dcbt_nmr) in proforma_map:
            continue

        new_proforma = entities.build_proforma(pf_data, account, "", dcbt_nmr)
        if not dry_run:
            new_id_hex = proforma_repository.save(proformas_col, new_proforma)
            new_proforma["_id_hex"] = new_id_hex
            pr = entities.build_proforma_request(new_proforma, "")
            proforma_request_repository.save(proforma_requests_col, pr)
        else:
            new_proforma["_id_hex"] = "dry_run_id"

        proforma_map[(account, dcbt_nmr)] = new_proforma
        created_dcbt_nmrs.add(dcbt_nmr)

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

    # ── Paso 8: construir billing y acumular updates masivos ──────────────────
    billing_updates = []

    # Procesar las órdenes del batch original
    for order in candidates:
        order_id = order.get("orderId", "")
        ref_order = order.get("referenceOrder", "")
        account = (order.get("seller") or {}).get("account", "")
        emission_date = order.get("emissionDate")
        if hasattr(emission_date, "isoformat"):
            emission_date = emission_date.isoformat()

        dcbt_nmr = ref_to_dcbt.get(ref_order)
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
            "proforma_action": proforma_action,
            "invoice_action": "SKIPPED",
            "billing_applied": billing_doc,
            "status": status_val,
            "reason": reason,
        }

        if proforma_action == "CREATED":
            result["proforma_created"] = {k: v for k, v in proforma_doc.items() if k != "_id"}

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
    if not dry_run:
        all_updates = billing_updates + extra_updates
        if all_updates:
            order_repository.bulk_write_billing(orders_col, all_updates)

    return results

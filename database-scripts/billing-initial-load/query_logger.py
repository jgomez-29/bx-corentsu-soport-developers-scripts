"""
Utilidad de logging de queries para billing-initial-load.

Activar con QUERY_LOGGING = True en config.py.
Imprime cada query Oracle o MongoDB antes de ejecutarse.
"""

import json

import config

_MAX_PARAMS_DISPLAY = 20  # si hay más de N params, muestra solo los primeros N


def _fmt_params(params: list) -> str:
    if not params:
        return "[]"
    if len(params) <= _MAX_PARAMS_DISPLAY:
        return str(params)
    return f"[{', '.join(str(p) for p in params[:_MAX_PARAMS_DISPLAY])}, ... ({len(params)} total)]"


def _fmt_doc(doc) -> str:
    try:
        return json.dumps(doc, default=str, ensure_ascii=False)
    except Exception:
        return str(doc)


def log_oracle(sql: str, params: list = None) -> None:
    """Imprime la query Oracle y sus parámetros si QUERY_LOGGING está activo."""
    if not config.QUERY_LOGGING:
        return
    sql_oneline = " ".join(sql.split())
    params_str = _fmt_params(params or [])
    print(f"  [ORACLE] {sql_oneline}")
    print(f"           params: {params_str}")


def log_mongo(collection: str, operation: str, filter_doc: dict = None, projection: dict = None) -> None:
    """Imprime la query MongoDB si QUERY_LOGGING está activo."""
    if not config.QUERY_LOGGING:
        return
    parts = [f"  [MONGO]  {collection}.{operation}"]
    if filter_doc is not None:
        parts.append(f"           filter: {_fmt_doc(filter_doc)}")
    if projection is not None:
        parts.append(f"           projection: {_fmt_doc(projection)}")
    print("\n".join(parts))

"""
Cliente Oracle para consultar el sistema legado SAM.

Encapsula la conexión a Oracle usando python-oracledb en modo thin
(sin necesidad de Oracle Instant Client instalado).

Tabla consultada: DCBT
    EEVV_NMR_ID     → ID de la orden de servicio en el legado
    DCBT_NMR_FAC_PF → Número de proforma asignado en el legado

Uso:
    from services.oracle_client import OracleConnection, fetch_proforma_ids_batch

    with OracleConnection(dsn=..., user=..., password=...) as connection:
        proforma_map = fetch_proforma_ids_batch(connection, ["REF-001", "REF-002"])
        # retorna {"REF-001": "PF-100", "REF-002": "PF-200"}
"""

from typing import Optional
import oracledb


class OracleConnection:
    """
    Context manager para conexión a Oracle en modo thin.

    No requiere Oracle Instant Client instalado. Cierra la conexión
    automáticamente al salir del bloque `with`.
    """

    def __init__(self, dsn: str, user: str, password: str):
        """
        Args:
            dsn:      DSN de conexión Oracle. Formato: 'host:port/service_name'
            user:     Usuario Oracle.
            password: Contraseña Oracle.
        """
        self.dsn = dsn
        self.user = user
        self.password = password
        self._connection: Optional[oracledb.Connection] = None

    def __enter__(self) -> oracledb.Connection:
        self._connection = oracledb.connect(
            user=self.user,
            password=self.password,
            dsn=self.dsn,
        )
        return self._connection

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._connection:
            self._connection.close()
        return False


def fetch_proforma_ids_batch(
    connection: oracledb.Connection,
    reference_order_ids: list,
) -> dict:
    """
    Consulta la tabla DCBT para obtener números de proforma en un lote.

    Ejecuta:
        SELECT EEVV_NMR_ID, DCBT_NMR_FAC_PF FROM DCBT
        WHERE EEVV_NMR_ID IN (:1, :2, ...)

    Usa bind variables posicionales para evitar SQL injection y permitir
    reutilización del plan de ejecución por parte del motor Oracle.

    Args:
        connection:          Conexión activa a Oracle.
        reference_order_ids: Lista de IDs de órdenes a consultar (máximo 1000).

    Returns:
        Dict {eevv_nmr_id: dcbt_nmr_fac_pf} con las proformas encontradas.
        Si un ID no está en la tabla DCBT, simplemente no aparece en el dict.
    """
    if not reference_order_ids:
        return {}

    placeholders = ", ".join(f":{i + 1}" for i in range(len(reference_order_ids)))
    query = f"SELECT EEVV_NMR_ID, DCBT_NMR_FAC_PF FROM DCBT WHERE EEVV_NMR_ID IN ({placeholders})"

    with connection.cursor() as cursor:
        cursor.execute(query, reference_order_ids)
        rows = cursor.fetchall()

    return {str(row[0]): str(row[1]) for row in rows if row[0] and row[1]}

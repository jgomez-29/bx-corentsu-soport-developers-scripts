"""
Cliente Oracle reutilizable para todos los scripts de database-scripts/.

Uso:
    from common.oracle.oracle_client import OracleConnection

    with OracleConnection(dsn="host:port/service", user="usr", password="pwd") as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 FROM DUAL")
            row = cursor.fetchone()
"""

import oracledb
from typing import Optional


class OracleConnection:
    """
    Context manager para conexión a Oracle DB en thin mode.
    Thin mode no requiere Oracle Instant Client; conecta directamente vía TCP.
    Cierra la conexión automáticamente al salir del bloque `with`.
    """

    def __init__(self, dsn: str, user: str, password: str):
        """
        Args:
            dsn:      DSN de conexión Oracle (ej: "host:1521/service_name")
            user:     Usuario Oracle
            password: Contraseña Oracle
        """
        if not dsn:
            raise ValueError(
                "ORACLE_DSN no está definida. Agrégala en el archivo .env de la raíz del repo.\n"
                "  Ejemplo: ORACLE_DSN=host:1521/service_name"
            )
        if not user:
            raise ValueError(
                "ORACLE_USER no está definida. Agrégala en el archivo .env de la raíz del repo.\n"
                "  Ejemplo: ORACLE_USER=usuario_oracle"
            )
        if not password:
            raise ValueError(
                "ORACLE_PASSWORD no está definida. Agrégala en el archivo .env de la raíz del repo.\n"
                "  Ejemplo: ORACLE_PASSWORD=contraseña_oracle"
            )
        # Forzar formato Easy Connect para evitar búsqueda en tnsnames.ora
        self.dsn = dsn if dsn.startswith("//") else f"//{dsn}"
        self.user = user
        self.password = password
        self._conn: Optional[oracledb.Connection] = None

    def __enter__(self) -> oracledb.Connection:
        self._conn = oracledb.connect(
            user=self.user,
            password=self.password,
            dsn=self.dsn,
        )
        return self._conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._conn:
            self._conn.close()
        return False

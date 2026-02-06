"""
Cliente MongoDB reutilizable para todos los scripts de database-scripts/.

Uso:
    from common.mongo.mongo_client import MongoConnection

    with MongoConnection(uri="mongodb://...", database="my_db") as db:
        collection = db["my_collection"]
        result = collection.find_one({"key": "value"})
"""

from pymongo import MongoClient
from typing import Optional


class MongoConnection:
    """
    Context manager para conexión a MongoDB.
    Cierra la conexión automáticamente al salir del bloque `with`.
    """

    def __init__(self, uri: str, database: str, timeout_ms: int = 5000):
        """
        Args:
            uri: URI de conexión a MongoDB (ej: "mongodb://host:port")
            database: Nombre de la base de datos
            timeout_ms: Timeout de conexión en milisegundos
        """
        self.uri = uri
        self.database_name = database
        self.timeout_ms = timeout_ms
        self._client: Optional[MongoClient] = None

    def __enter__(self):
        self._client = MongoClient(
            self.uri,
            serverSelectionTimeoutMS=self.timeout_ms,
        )
        # Verificar conexión
        self._client.admin.command("ping")
        return self._client[self.database_name]

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            self._client.close()
        return False

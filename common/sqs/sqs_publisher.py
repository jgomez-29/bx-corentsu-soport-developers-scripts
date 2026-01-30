import asyncio
from typing import List, Dict, Any, Optional, Callable
import boto3
from botocore.config import Config
import json
import os
from datetime import datetime, timezone
import time
from .message_builder import MessageBuilder

class SQSPublisher:
    def __init__(
        self,
        queue_url: str,
        region_name: str = 'us-east-1',
        max_concurrent: int = 10,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_session_token: Optional[str] = None,
        profile_name: Optional[str] = None,
        envelope_builder: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
    ):
        """Inicializa el publicador SQS.
        Credenciales pueden venir por:
        1. Parámetros del constructor
        2. Variables de entorno estándar: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN, AWS_PROFILE, AWS_REGION
        3. Configuración por perfil (~/.aws/credentials)
        Si no se provee nada, boto3 hará su resolución normal de credenciales.
        """
        self.queue_url = queue_url
        self.region_name = region_name or os.getenv('AWS_REGION', 'us-east-1')

        # Resolver credenciales desde entorno si no se pasaron
        aws_access_key_id = aws_access_key_id or os.getenv('AWS_ACCESS_KEY_ID')
        aws_secret_access_key = aws_secret_access_key or os.getenv('AWS_SECRET_ACCESS_KEY')
        aws_session_token = aws_session_token or os.getenv('AWS_SESSION_TOKEN')
        profile_name = profile_name or os.getenv('default')

        # Crear sesión según lo disponible
        if profile_name:
            self.session = boto3.session.Session(profile_name=profile_name, region_name=self.region_name)
        elif aws_access_key_id and aws_secret_access_key:
            self.session = boto3.session.Session(
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                aws_session_token=aws_session_token,
                region_name=self.region_name,
            )
        else:
            self.session = boto3.session.Session(region_name=self.region_name)

        self.client = self.session.client('sqs', region_name=self.region_name, config=Config(retries={'max_attempts': 3}))
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.envelope_builder = envelope_builder or MessageBuilder.build_order

    async def _send_single(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        async with self.semaphore:
            try:
                envelope = self.envelope_builder(payload)
                response = await asyncio.to_thread(
                    self.client.send_message,
                    QueueUrl=self.queue_url,
                    MessageBody=json.dumps(envelope, ensure_ascii=False)
                )
                return {"status": "OK", "messageId": response.get("MessageId"), "refId": payload.get("orderId") or payload.get("trackingId")}
            except Exception as e:
                print(f"[SQS ERROR] refId={payload.get('orderId') or payload.get('trackingId')} queue={self.queue_url} region={self.region_name} error={e}")
                return {"status": "ERROR", "error": str(e), "refId": payload.get("orderId") or payload.get("trackingId")}

    async def publish_batch(self, payloads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        tasks = [self._send_single(p) for p in payloads]
        return await asyncio.gather(*tasks)

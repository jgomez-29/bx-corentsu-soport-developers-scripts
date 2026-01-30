"""
Publicador a SNS Topic. Usa el mismo envelope_builder que SQS;
extrae Message y MessageAttributes y los envía con sns.publish().
"""
import asyncio
from typing import List, Dict, Any, Optional, Callable
import boto3
from botocore.config import Config
import json
import os


def _envelope_attributes_to_sns(attributes: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    """Convierte MessageAttributes del envelope (Type/Value) al formato SNS (DataType/StringValue)."""
    if not attributes:
        return {}
    result = {}
    for name, attrs in attributes.items():
        if not isinstance(attrs, dict):
            continue
        data_type = attrs.get("Type") or attrs.get("DataType") or "String"
        value = attrs.get("Value") or attrs.get("StringValue") or ""
        result[name] = {"DataType": data_type, "StringValue": str(value)}
    return result


class SNSPublisher:
    def __init__(
        self,
        topic_arn: str,
        region_name: str = "us-east-1",
        max_concurrent: int = 10,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_session_token: Optional[str] = None,
        profile_name: Optional[str] = None,
        envelope_builder: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
    ):
        self.topic_arn = topic_arn
        self.region_name = region_name or os.getenv("AWS_REGION", "us-east-1")

        aws_access_key_id = aws_access_key_id or os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_access_key = aws_secret_access_key or os.getenv("AWS_SECRET_ACCESS_KEY")
        aws_session_token = aws_session_token or os.getenv("AWS_SESSION_TOKEN")
        profile_name = profile_name or os.getenv("AWS_PROFILE")

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

        self.client = self.session.client(
            "sns", region_name=self.region_name, config=Config(retries={"max_attempts": 3})
        )
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.envelope_builder = envelope_builder

    async def _publish_single(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        async with self.semaphore:
            try:
                envelope = self.envelope_builder(payload)
                message = envelope.get("Message")
                if message is None:
                    message = json.dumps(payload, ensure_ascii=False)
                elif isinstance(message, dict):
                    message = json.dumps(message, ensure_ascii=False)

                raw_attrs = envelope.get("MessageAttributes") or {}
                sns_attrs = _envelope_attributes_to_sns(raw_attrs)

                kwargs = {"TopicArn": self.topic_arn, "Message": message}
                if sns_attrs:
                    kwargs["MessageAttributes"] = sns_attrs

                response = await asyncio.to_thread(self.client.publish, **kwargs)
                ref_id = (
                    payload.get("orderId")
                    or payload.get("trackingId")
                    or payload.get("siiFolio")
                    or payload.get("proformaSerie")
                )
                return {"status": "OK", "messageId": response.get("MessageId"), "refId": ref_id}
            except Exception as e:
                ref_id = (
                    payload.get("orderId")
                    or payload.get("trackingId")
                    or payload.get("siiFolio")
                    or payload.get("proformaSerie")
                )
                print(f"[SNS ERROR] refId={ref_id} topic={self.topic_arn} region={self.region_name} error={e}")
                return {"status": "ERROR", "error": str(e), "refId": ref_id}

    async def publish_batch(self, payloads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        tasks = [self._publish_single(p) for p in payloads]
        return await asyncio.gather(*tasks)


class DualPublisher:
    """Envía a SQS y SNS; publish_batch devuelve OK solo si ambos tuvieron éxito."""
    def __init__(self, sqs_publisher: Any, sns_publisher: "SNSPublisher"):
        self.sqs = sqs_publisher
        self.sns = sns_publisher

    async def publish_batch(self, payloads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results_sqs = await self.sqs.publish_batch(payloads)
        results_sns = await self.sns.publish_batch(payloads)
        merged = []
        for a, b in zip(results_sqs, results_sns):
            ok = a.get("status") == "OK" and b.get("status") == "OK"
            merged.append({
                "status": "OK" if ok else "ERROR",
                "refId": a.get("refId") or b.get("refId"),
                "error": None if ok else (a.get("error") or b.get("error")),
            })
        return merged

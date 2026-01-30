import json
import os
import uuid
import time
from datetime import datetime, timezone
from typing import Dict, Any

DEFAULT_DOMAIN = os.getenv('EVENT_DOMAIN', 'corentsu')
DEFAULT_SUBDOMAIN = os.getenv('EVENT_SUBDOMAIN', 'ciclos')
DEFAULT_BUSINESS = os.getenv('EVENT_BUSINESS_CAPACITY', 'ciclos')
DEFAULT_CHANNEL = os.getenv('EVENT_CHANNEL', 'web')
DEFAULT_VERSION = os.getenv('EVENT_VERSION', '1.0')
DEFAULT_TOPIC_ARN = os.getenv('TOPIC_ARN', 'arn:aws:sns:us-east-1:000000000000:placeholder-topic')

class MessageBuilder:
    """Crea el envelope genérico para distintas entidades"""
    @staticmethod
    def _utc_ts() -> str:
        return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')

    @staticmethod
    def _epoch() -> int:
        return int(time.time())

    @classmethod
    def build_envelope(
        cls,
        payload: Dict[str, Any],
        entity_type: str,
        event_type: str,
        domain: str = DEFAULT_DOMAIN,
        subdomain: str = DEFAULT_SUBDOMAIN,
        business_capacity: str = DEFAULT_BUSINESS,
        channel: str = DEFAULT_CHANNEL,
        version: str = DEFAULT_VERSION,
        topic_arn: str = DEFAULT_TOPIC_ARN,
    ) -> Dict[str, Any]:
        epoch_seconds = cls._epoch()
        body_attributes = {
            'eventId': {'Type': 'String', 'Value': str(uuid.uuid4())},
            'datetime': {'Type': 'String', 'Value': cls._utc_ts()},
            'businessCapacity': {'Type': 'String', 'Value': business_capacity},
            'entityType': {'Type': 'String', 'Value': entity_type},
            'domain': {'Type': 'String', 'Value': domain},
            'channel': {'Type': 'String', 'Value': channel},
            'subdomain': {'Type': 'String', 'Value': subdomain},
            'eventType': {'Type': 'String', 'Value': event_type},
            'version': {'Type': 'String', 'Value': version},
            'timestamp': {'Type': 'Number', 'Value': str(epoch_seconds)}
        }
        return {
            'Type': 'Notification',
            'MessageId': str(uuid.uuid4()),
            'TopicArn': topic_arn,
            'Message': json.dumps(payload, ensure_ascii=False),
            'Timestamp': cls._utc_ts(),
            'SignatureVersion': '1',
            'Signature': 'NA',
            'SigningCertURL': 'NA',
            'UnsubscribeURL': 'NA',
            'MessageAttributes': body_attributes
        }

    @classmethod
    def build_order(cls, order: Dict[str, Any]) -> Dict[str, Any]:
        return cls.build_envelope(order, entity_type='order', event_type='orderModified')
    
    
    @classmethod
    def build_proforma(cls, proforma: Dict[str, Any]) -> Dict[str, Any]:
        return cls.build_envelope(proforma, entity_type='proforma', event_type='ProformaCreated')

    @classmethod
    def build_billing_document(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Construye envelope para billing document request"""
        return cls.build_envelope(
            payload,
            entity_type='DocumentRequest',
            event_type='billingOrderRequested',
            subdomain='finmg',
            business_capacity='billing'
        )

    @classmethod
    def build_tracking_event(cls, event_doc: Dict[str, Any]) -> Dict[str, Any]:
        # event_doc ya contiene el cuerpo que irá en Message
        return cls.build_envelope(event_doc, entity_type='checkpoint', event_type='checkpointCreated')

    @classmethod
    def build_sale_transmission(cls, sale_transmission: Dict[str, Any], event_type: str = 'SaleDispatched') -> Dict[str, Any]:
        """Construye envelope para SaleTransmission
        
        Args:
            sale_transmission: Objeto SaleTransmission
            event_type: Tipo de evento (default: 'SaleDispatched' para que coincida con el filtro SNS)
        """
        return cls.build_envelope(
            sale_transmission,
            entity_type='saleTransmission',
            event_type=event_type,
            subdomain='finmg',
            business_capacity='finmg',
            channel='web'
        )

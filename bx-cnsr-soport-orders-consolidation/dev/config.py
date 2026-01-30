"""
Configuración ESPECÍFICA para DEV - Orders consolidation.

Sensible (solo en .env): AWS_REGION, AWS_ACCOUNT_ID.
Nombres de recurso (no sensible) aquí en config.
"""
import os

REGION = os.getenv("AWS_REGION")
AWS_ACCOUNT_ID = os.getenv("AWS_ACCOUNT_ID")

QUEUE_NAME = "queue-soport-erp-orders-consolidation-01"
TOPIC_NAME = None

QUEUE_URL = f"https://sqs.{REGION}.amazonaws.com/{AWS_ACCOUNT_ID}/{QUEUE_NAME}" if (REGION and AWS_ACCOUNT_ID) else None
TOPIC_ARN = f"arn:aws:sns:{REGION}:{AWS_ACCOUNT_ID}:{TOPIC_NAME}" if (REGION and AWS_ACCOUNT_ID and TOPIC_NAME) else None

"""
Configuración ESPECÍFICA para DEV - Replicate Invoice (queue-finmg-billing-replicated).

Sensible (solo en .env): AWS_REGION, AWS_ACCOUNT_ID.
Nombres de recurso (no sensible) aquí en config.
La configuración general está en ../config.py
"""
import os

REGION = os.getenv("AWS_REGION")
AWS_ACCOUNT_ID = os.getenv("AWS_ACCOUNT_ID")

# Nombres de recursos (no sensibles)
QUEUE_NAME = "queue-finmg-billing-replicated"
TOPIC_NAME = None  # Sin topic SNS para este caso

QUEUE_URL = f"https://sqs.{REGION}.amazonaws.com/{AWS_ACCOUNT_ID}/{QUEUE_NAME}" if (REGION and AWS_ACCOUNT_ID) else None
TOPIC_ARN = f"arn:aws:sns:{REGION}:{AWS_ACCOUNT_ID}:{TOPIC_NAME}" if (REGION and AWS_ACCOUNT_ID and TOPIC_NAME) else None

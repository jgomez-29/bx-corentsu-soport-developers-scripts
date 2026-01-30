"""
Configuración ESPECÍFICA para DEV - payment-process-fragment.

Sensible (solo en .env): AWS_REGION, AWS_ACCOUNT_ID.
Nombres de recurso (no sensible) aquí en config.
"""
import os

REGION = os.getenv("AWS_REGION")
AWS_ACCOUNT_ID = os.getenv("AWS_ACCOUNT_ID")

QUEUE_NAME = None
TOPIC_NAME = "topic-finmg-payment-process-fragment"

QUEUE_URL = None
TOPIC_ARN = f"arn:aws:sns:{REGION}:{AWS_ACCOUNT_ID}:{TOPIC_NAME}" if (REGION and AWS_ACCOUNT_ID and TOPIC_NAME) else None

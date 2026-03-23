"""
Configuración ESPECÍFICA para DEV - proforma-checkpoints (SQS).

Sensible (solo en .env): AWS_REGION, AWS_ACCOUNT_ID.
Nombres de recurso (no sensible) aquí en config.
La configuración general está en ../config.py
"""

import os

REGION = os.getenv("AWS_REGION")
AWS_ACCOUNT_ID = os.getenv("AWS_ACCOUNT_ID")

QUEUE_NAME = "queue-finmg-proforma-checkpoints"

QUEUE_URL = (
    f"https://sqs.{REGION}.amazonaws.com/{AWS_ACCOUNT_ID}/{QUEUE_NAME}"
    if (REGION and AWS_ACCOUNT_ID)
    else None
)

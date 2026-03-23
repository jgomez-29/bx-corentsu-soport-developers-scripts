"""
Builder del body para el endpoint generate-bulk-request-id.

El fileName se genera dinámicamente por request, equivalente a las
funciones de JMeter:
    ${__time(yyyyMMddHHmmss)} → datetime.now().strftime("%Y%m%d%H%M%S")
    ${__threadNum}            → número secuencial del request
    ${__Random(1,10000)}      → random.randint(1, 10000)
"""

import random
from datetime import datetime
from typing import Any, Dict


def build_body(request_num: int) -> Dict[str, Any]:
    """
    Construye el body del request con un fileName único.

    Args:
        request_num: Número secuencial del request actual (equivalente a __threadNum)

    Returns:
        Dict con "fileName" generado dinámicamente
    """
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_num = random.randint(1, 10000)
    return {"fileName": f"notas_credito_{timestamp}_{request_num}_{random_num}.xlsx"}

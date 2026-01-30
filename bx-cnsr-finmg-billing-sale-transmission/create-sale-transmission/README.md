# Script de Envío de Mensajes a SQS - Sale Transmission (CreateSaleTransmissionUseCase)

Script para enviar mensajes a la queue `queue-finmg-sales-transmission` para procesar SaleTransmission mediante el `CreateSaleTransmissionUseCase`.

## 📁 Estructura

```
CreateSaleTransmission/
├── sale_transmission_builder.py    # Lógica común para cargar/generar SaleTransmission
├── send_message.py                   # Script principal (común)
├── README.md                        # Esta documentación
│
├── dev/                             # Ambiente DEV
│   ├── config.py                    # Configuración DEV (queue, región)
│   ├── entities/
│   │   └── sale-transmission.json   # Datos de ejemplo para DEV
│   └── logs/                        # Logs de DEV
│
└── qa/                              # Ambiente QA
    ├── config.py                    # Configuración QA (queue, región)
    ├── entities/
    │   └── sale-transmission.json   # Datos de ejemplo para QA
    └── logs/                        # Logs de QA
```

## 🚀 Uso

### Paso 1: Seleccionar ambiente

Navega al folder del ambiente que quieres usar:

```bash
# Para DEV
cd dev/

# O para QA
cd qa/
```

### Paso 2: Configurar

Edita `config.py` según tus necesidades:

```python
# Opción 1: Cargar desde archivo JSON
INPUT_FILE = "./entities/sale-transmission.json"
SALE_TRANSMISSIONS_LIST = []
MAX_MESSAGES = 1  # 0 = todos

# Opción 2: Pruebas de estrés (genera mensajes automáticamente)
STRESS_TEST_ENABLED = True
STRESS_TEST_BASE_SII_FOLIO = "TEST-SII"
STRESS_TEST_START = 1
MAX_MESSAGES = 1000  # Cantidad de mensajes a generar
```

### Paso 3: Ejecutar

Desde dentro del folder del ambiente (dev/ o qa/):

```bash
python ../send_message.py
```

## 📋 Campos Mínimos Requeridos

El `SaleTransmission` debe contener los siguientes campos obligatorios:

### Para `type: "order"`:
```json
{
  "society": "1700",              // String - obligatorio
  "type": "order",                // String - obligatorio
  "siiFolio": "13754",            // String - obligatorio
  "docType": 16,                  // Integer - obligatorio
  "account": "44298540-1-85",     // String - obligatorio
  "costDetail": {                 // CostDetail - obligatorio
    "amount": 722,
    "taxableAmount": 607,
    "tax": 115,
    "currency": "CLP",
    "discount": {                 // Opcional
      "amount": 0,
      "isFull": false
    }
  },
  "prepaidEmission": {            // PrepaidEmission - OBLIGATORIO para type="order"
    "orderId": "1030166476",
    "paymentType": "PEPD",
    "transactionId": "00000223912261",
    "method": "CC",
    "collector": "GETNET",         // Opcional
    "customerInfo": {
      "identifier": "66666666-6",
      "name": "John Dwayne",
      "address": "456 Side St 789"
    },
    "amount": 607
  },
  "emissionDate": "2026-01-28T00:00:00.000Z",  // Opcional
  "createdBy": "user1"             // Opcional
}
```

### Para `type: "proforma"` o `type: "invoice"`:
```json
{
  "society": "1700",              // String - obligatorio
  "type": "proforma",             // String - "proforma" o "invoice" - obligatorio
  "siiFolio": "2277",             // String - obligatorio
  "docType": 12,                  // Integer - obligatorio
  "account": "96801150-54-8",       // String - obligatorio
  "costDetail": {                 // CostDetail - obligatorio
    "amount": 26369,
    "taxableAmount": 22159,
    "tax": 4210,
    "currency": "CLP"
    // discount es opcional
  },
  // prepaidEmission NO se requiere para proforma/invoice
  "emissionDate": "2025-12-22T00:00:00.000Z",  // Opcional
  "createdBy": "kevin.lorca@blue.cl"  // Opcional
}
```

### ⚠️ Campos que NO se deben enviar

Los siguientes campos se calculan automáticamente por el `CreateSaleTransmissionUseCase` y **NO deben incluirse** en el mensaje:

- `docClass` - Se calcula desde EquivalenceCatalog usando `docType`
- `docTypeDescription` - Se calcula automáticamente
- `dummy` - Se calcula según lógica de negocio
- `status` - Se calcula automáticamente ("CREATED" o "SAP_BP_NOT_FOUND")
- `cenco` - Se calcula según `account` (termina en "-45" → "700E05G64", sino → "1700E05G38")
- `paymentKey` - Se calcula según días de crédito del cliente
- `createdAt` - Se calcula automáticamente
- `updatedAt` - Se calcula automáticamente

## 🔧 Configuración

### Configuración por Ambiente

Cada ambiente (dev/, qa/) tiene su propio `config.py` con:

- **Queue URL**: Diferente por ambiente
- **Región AWS**: DEV usa `us-west-2`, QA usa `us-east-1`
- **Datos de ejemplo**: Cada ambiente puede tener sus propios datos en `entities/`

### Variables de Entorno

En el archivo `.env` en la raíz del repo solo se usan datos sensibles:

- `AWS_REGION`: Región de AWS
- `AWS_ACCOUNT_ID`: ID de la cuenta AWS

Los nombres de la cola y del topic están en `dev/config.py` y `qa/config.py` (`QUEUE_NAME`, `TOPIC_NAME`).

## 📊 Modos de Operación

### Modo 1: Cargar desde archivo JSON

1. Edita `config.py`:
   ```python
   INPUT_FILE = "./entities/sale-transmission.json"
   SALE_TRANSMISSIONS_LIST = []
   MAX_MESSAGES = 10  # Limitar cantidad
   ```

2. Crea o edita `./entities/sale-transmission.json`:
   ```json
   [
     {
       "society": "1700",
       "type": "order",
       "siiFolio": "13754",
       ...
     }
   ]
   ```

3. Ejecuta: `python ../send_message.py`

### Modo 2: Pruebas de Estrés

Genera múltiples mensajes automáticamente para pruebas de carga:

1. Edita `config.py`:
   ```python
   STRESS_TEST_ENABLED = True
   STRESS_TEST_BASE_SII_FOLIO = "TEST-SII"
   STRESS_TEST_START = 1
   MAX_MESSAGES = 1000
   STRESS_TEST_TEMPLATE_FILE = "./entities/sale-transmission.json"
   ```

2. El script generará mensajes con `siiFolio` incrementales:
   - TEST-SII-000001
   - TEST-SII-000002
   - ...
   - TEST-SII-001000

3. Ejecuta: `python ../send_message.py`

## 📝 Logs

Todos los `siiFolios` procesados se guardan automáticamente en archivos JSON dentro de la carpeta `./logs/`. Los archivos se generan con nombres descriptivos que incluyen la fecha/hora:

- `sii_folios_20260128_143022.json`

Cada archivo contiene:
- El total de `siiFolios` procesados
- La lista completa de `siiFolios`
- Un timestamp de cuando se generó

## 🔍 Verificación

El script muestra información de verificación del primer mensaje antes de enviar:

```
=== VERIFICACIÓN DEL ENVELOPE (primer mensaje) ===
SiiFolio: 13754
Type: order
Account: 44298540-1-85
Message es string: True
MessageAttributes.eventType.Value: create
===============================
```

## ⚙️ Lógica del CreateSaleTransmissionUseCase

El consumer procesa los mensajes de la siguiente manera:

1. **Recibe el mensaje SQS** con estructura `MessageSQS`
2. **Parsea** el campo `Message` (JSON string) a `SaleTransmission`
3. **Calcula campos automáticamente**:
   - `docClass`: desde EquivalenceCatalog usando `docType`
   - `dummy`: según lógica de negocio (agencia, partner, collector, method)
   - `cenco`: según `account` (termina en "-45" → "700E05G64", sino → "1700E05G38")
   - `paymentKey`: según días de crédito del cliente
   - `status`: "CREATED" o "SAP_BP_NOT_FOUND"
4. **Verifica unicidad**: busca por `siiFolio` + `docClass` + `society`
   - Si existe → UPDATE
   - Si no existe → INSERT

## 🎯 Ejemplo de Uso para Pruebas de Estrés

```bash
# 1. Ir al ambiente deseado
cd dev/

# 2. Editar config.py
# STRESS_TEST_ENABLED = True
# MAX_MESSAGES = 5000

# 3. Ejecutar
python ../send_message.py
```

Esto generará 5000 mensajes con `siiFolio` incrementales` para probar el rendimiento del `CreateSaleTransmissionUseCase`.

## 📚 Referencias

- Queue: `queue-finmg-sales-transmission`
- UseCase: `CreateSaleTransmissionUseCase`
- Repositorio: `bx-cnsr-finmg-billing-sales-transmission`

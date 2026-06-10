# Guía de Testing Manual - Sistema de Billing

Datos de prueba creados con: `python scripts/setup_test_billing.py`

## 📋 Credenciales

### BU #1: Test Abogados (Plan STARTER)
```
Email: admin@test-abogados.es
Contraseña: password123
BU Code: TEST_ABAN
Límites: 100 docs/mes, 200 extracciones/mes
Overage: SÍ (0,20€/doc, 0,10€/extracción)
```

### BU #2: Test Startup (Plan GRATUITO)
```
Email: dev@test-startup.es
Contraseña: password123
BU Code: TEST_STARTUP
Límites: 10 docs/mes, 20 extracciones/mes
Overage: NO (rechaza)
```

---

## 🧪 Casos de Testing

### TEST 1: Login y obtener token
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@test-abogados.es",
    "password": "password123"
  }'
```

**Esperado:**
```json
{
  "access_token": "eyJ0...",
  "refresh_token": "eyJ0...",
  "user": { ... }
}
```

---

### TEST 2: Subir documento #1-79 (sin avisos)
```bash
curl -X POST http://localhost:8000/documents \
  -H "Authorization: Bearer {access_token}" \
  -H "X-BU-ID: TEST_ABAN" \
  -F "file=@factura1.pdf"
```

**Esperado:**
```json
{
  "id": "uuid",
  "title": "factura1.pdf",
  "status": "pending",
  "quota_warning": null    # Sin aviso
}
```

---

### TEST 3: Subir documento #80 (aviso 80%)
```bash
curl -X POST http://localhost:8000/documents \
  -H "Authorization: Bearer {access_token}" \
  -H "X-BU-ID: TEST_ABAN" \
  -F "file=@factura80.pdf"
```

**Esperado:**
```json
{
  "id": "uuid",
  "quota_warning": {
    "type": "approaching_limit",
    "metric": "documents",
    "current_usage": 80,
    "limit": 100,
    "percentage": 80,
    "days_left": 21
  }
}
```

---

### TEST 4: Subir documento #90 (aviso 90%)
Similar al anterior, pero `percentage: 90`

---

### TEST 5: Subir documento #95 (aviso 95%)
Similar al anterior, pero `percentage: 95`

---

### TEST 6: Subir documento #101 (OVERAGE - se cobra)
```bash
curl -X POST http://localhost:8000/documents \
  -H "Authorization: Bearer {access_token}" \
  -H "X-BU-ID: TEST_ABAN" \
  -F "file=@factura101.pdf"
```

**Esperado:**
```json
{
  "id": "uuid",
  "quota_warning": {
    "type": "overage_charge",
    "metric": "documents",
    "current_usage": 101,
    "limit": 100,
    "overage_units": 1,
    "overage_cost_eur": 0.20
  }
}
```

---

### TEST 7: Extracciones con avisos
Mismo patrón que documentos, pero:

```bash
curl -X POST http://localhost:8000/extract \
  -H "Authorization: Bearer {access_token}" \
  -H "X-BU-ID: TEST_ABAN" \
  -H "Content-Type: application/json" \
  -d '{
    "config_id": "{prompt_config_id}",
    "document_text": "Factura con datos...",
    "document_name": "factura1.pdf"
  }'
```

Avisos en:
- 160 extracciones: approaching 80%
- 180 extracciones: approaching 90%
- 190 extracciones: approaching 95%
- 201 extracciones: overage_charge (0,10€)

---

## ⛔ TEST 8: Plan GRATUITO rechaza overages

### Login con Test Startup
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "dev@test-startup.es",
    "password": "password123"
  }'
```

### Subir 10 documentos (OK)
```bash
# Doc 1-10: sin problemas, sin avisos
```

### Intentar subir documento #11 (RECHAZADO)
```bash
curl -X POST http://localhost:8000/documents \
  -H "Authorization: Bearer {access_token}" \
  -H "X-BU-ID: TEST_STARTUP" \
  -F "file=@factura11.pdf"
```

**Esperado: Error 429**
```json
{
  "detail": "Cuota de documentos alcanzada (máx 10/mes). Plan free no permite overages."
}
```

---

## 📊 TEST 9: Verificar eventos en BD

```sql
-- Eventos de Test Abogados
SELECT 
  event_type,
  SUM(quantity) as total,
  COUNT(*) as count
FROM usage_events
WHERE bu_id IN (SELECT id FROM business_units WHERE code = 'TEST_ABAN')
GROUP BY event_type
ORDER BY event_type;

-- Resultado esperado:
-- doc.uploaded         | 101 | 101
-- extraction.run       | 201 | 201
-- overage.doc.upload   | 100 | 1  (5 docs extra × 20 cents)
-- overage.extraction   | 10  | 1  (1 extraccion extra × 10 cents)
```

---

## 🔍 Puntos clave a verificar

1. ✅ Avisos aparecen SOLO en las métricas específicas (80%, 90%, 95%, overage)
2. ✅ Avisos incluyen siempre `days_left` (aproximadamente 20-30)
3. ✅ Plan GRATUITO rechaza con 429, no aviso
4. ✅ Plan STARTER permite overage + aviso
5. ✅ Los eventos se registran correctamente en `usage_events`
6. ✅ Los costos están en céntimos de euro (20 = 0,20€)

---

## 🚀 Próximos pasos

Después de validar estos tests manuales:
1. Fase 3B: Generar invoices (cron 1º de mes)
2. Fase 4: API de invoices (GET, PATCH mark-paid)
3. Email automáticos de avisos (opcional)

---

## 💡 Tips útiles

### Para generar múltiples documentos rápido:
```bash
#!/bin/bash
TOKEN="eyJ0..."
BU="TEST_ABAN"

for i in {1..105}; do
  echo "Subiendo doc $i..."
  curl -X POST http://localhost:8000/documents \
    -H "Authorization: Bearer $TOKEN" \
    -H "X-BU-ID: $BU" \
    -F "file=@dummy.txt" \
    -s | jq '.quota_warning'
  sleep 0.5
done
```

### Para ver respuesta completa:
```bash
curl -X POST ... | jq '.'
```

### Para ver solo los avisos:
```bash
curl -X POST ... | jq '.quota_warning'
```

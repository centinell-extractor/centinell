# Modelo de Facturación - Centinell

## Planes

### 1. GRATUITO (free)
- **Precio:** 0€/mes
- **Documentos/mes:** 10
- **Extracciones/mes:** 20
- **Usuarios:** 1
- **API keys:** 2 máximo
- **Rate limit:** 10 req/min
- **Soporte:** Comunidad (documentación)
- **Overage permitido:** No
- **Código:** `free`

### 2. STARTER (starter)
- **Precio:** 19€/mes
- **Documentos/mes:** 100
- **Extracciones/mes:** 200
- **Usuarios:** 3
- **API keys:** Ilimitadas
- **Rate limit:** 100 req/min
- **Soporte:** Email (48h)
- **Overage permitido:** Sí
  - Doc extra: 0,20€ c/u
  - Extracción extra: 0,10€ c/u
  - Usuario extra: 5€ c/u
- **Código:** `starter`

### 3. BUSINESS (business)
- **Precio:** 79€/mes
- **Documentos/mes:** 1000
- **Extracciones/mes:** 2500
- **Usuarios:** 20
- **API keys:** Ilimitadas
- **Rate limit:** 500 req/min
- **Soporte:** Email prioritario (24h)
- **Overage permitido:** Sí
  - Doc extra: 0,15€ c/u
  - Extracción extra: 0,08€ c/u
  - Usuario extra: 3€ c/u
- **Código:** `business`

### 4. ENTERPRISE (enterprise)
- **Precio:** Custom (contactar)
- **Documentos/mes:** Ilimitado
- **Extracciones/mes:** Ilimitado
- **Usuarios:** Ilimitado
- **API keys:** Ilimitadas
- **Rate limit:** Ilimitado
- **Soporte:** Dedicado 24/7
- **SLA:** 99.9% uptime
- **Overage permitido:** No aplica
- **Código:** `enterprise`

---

## Mecanismo de Control

### Workflow al hacer upload/extracción:

```
1. Usuario intenta acción (upload doc / run extraction)
2. Sistema obtiene plan actual de la BU
3. Verifica: ¿Se excede la cuota de este mes?
   ├─ NO → ✅ Proceder, registrar evento de uso
   ├─ SÍ (plan sin overage) → ❌ Rechazar con 403 "Quota exceeded"
   └─ SÍ (plan con overage) → ✅ Proceder + cobrar overage
4. Al fin de mes:
   - Calcular consumo real
   - Generar invoice (plan_price + overages)
   - Marcar como "pending" para cobro
```

### Verificación de límites (pseudocódigo):

```python
async def check_quota(db, bu_id, action_type):
    """
    action_type: "doc.upload", "extraction.run", etc.
    Retorna: (allowed: bool, cost_if_overage: int_cents)
    """
    plan = await get_active_plan(bu_id)
    usage = await get_month_usage(bu_id, month=now())
    
    if action_type == "doc.upload":
        if usage.docs_uploaded >= plan.max_docs_per_month:
            if plan.allow_overage:
                return True, plan.overage_doc_cents
            else:
                return False, 0
    
    # Similar para extractions, etc.
    return True, 0
```

---

## Facturación

### Proceso mensual (1º del mes):

```
Para cada BU:
  1. Obtener plan vigente durante mes anterior
  2. Calcular consumo real (query usage_events)
  3. Calcular overages si aplica
  4. Generar Invoice con:
     - plan_price_cents (ej: 1900 = $19)
     - overage_docs + overage_docs_cost_cents
     - overage_extractions + overage_extractions_cost_cents
     - overage_users + overage_users_cost_cents
     - total_cents = suma de todo
  5. Marcar invoice status = "pending" (en espera de pago)
  6. Enviar email: "Tu factura está lista"
```

### Estados de Invoice:

```
pending   → Generada, esperando pago
paid      → Pagado (manual o webhook de Stripe)
overdue   → No pagado después de 15 días
suspended → No pagado después de 30 días (acceso suspendido)
refunded  → Reembolsado
```

---

## Restricciones por estado de suscripción

| Estado | Puede usar API? | Puede subir docs? | Comentario |
|--------|-----------------|-------------------|-----------|
| Activa (pagado) | ✅ Sí | ✅ Sí | Normal |
| Pending | ✅ Sí | ✅ Sí | Gracia de 7 días |
| Overdue | ⚠️ Sí | ⚠️ Limitado (warning) | Debe pagar pronto |
| Suspended | ❌ No | ❌ No | Acceso bloqueado |

---

## Cambios en BD necesarios

### Actualizar tabla `plans`:

```sql
ALTER TABLE plans ADD COLUMN IF NOT EXISTS (
    allow_overage BOOLEAN DEFAULT true,
    overage_doc_cents INTEGER DEFAULT 20,
    overage_extraction_cents INTEGER DEFAULT 10,
    overage_user_cents INTEGER DEFAULT 500
);
```

### Nueva tabla `invoices`:

```sql
CREATE TABLE invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bu_id UUID NOT NULL REFERENCES business_units(id),
    period_month DATE NOT NULL,  -- "2026-05-01"
    plan_id UUID REFERENCES plans(id),
    
    -- Cargos
    plan_price_cents INTEGER NOT NULL DEFAULT 0,
    
    overage_docs INTEGER DEFAULT 0,
    overage_docs_cost_cents INTEGER DEFAULT 0,
    
    overage_extractions INTEGER DEFAULT 0,
    overage_extractions_cost_cents INTEGER DEFAULT 0,
    
    overage_users INTEGER DEFAULT 0,
    overage_users_cost_cents INTEGER DEFAULT 0,
    
    total_cents INTEGER NOT NULL,
    
    -- Estado
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending, paid, overdue, suspended
    paid_at TIMESTAMP NULL,
    
    -- Auditoría
    created_at TIMESTAMP DEFAULT now(),
    created_by UUID REFERENCES users(id),
    
    CONSTRAINT unique_bu_period UNIQUE (bu_id, period_month),
    INDEX idx_invoices_bu (bu_id),
    INDEX idx_invoices_status (status),
    INDEX idx_invoices_period (period_month)
);
```

---

## Fechas clave

- **Ciclo de facturación:** Mes natural (1º al último día)
- **Período de gracia:** 7 días sin pago
- **Período de mora:** 15 días sin pago (enviar recordatorio)
- **Suspensión:** 30 días sin pago

---

## Integraciones futuras

- **Stripe:** Webhooks para pagos automáticos
- **Email:** Recordatorios de vencimiento
- **Analytics:** Dashboard de ingresos/proyecciones
- **API:** Endpoint para que admin vea invoices

---

## Notas

- Plan GRATUITO nunca genera invoice (price = 0)
- Plan ENTERPRISE: contacto manual, sin automation
- Overage se calcula en tiempo real, se suma a invoice mensual
- UsageEvent es la fuente de verdad (append-only)

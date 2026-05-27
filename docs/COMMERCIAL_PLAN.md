# Centinell — Plan Comercial
**Versión:** 1.0 | **Fecha:** Mayo 2026 | **Confidencial**

---

## Índice

1. [Propuesta de valor](#1-propuesta-de-valor)
2. [Modelo de negocio](#2-modelo-de-negocio)
3. [Estructura de tarifas](#3-estructura-de-tarifas)
4. [Cómo justificar los honorarios](#4-cómo-justificar-los-honorarios)
5. [Cómo monitorear y controlar el uso](#5-cómo-monitorear-y-controlar-el-uso)
6. [Costes de infraestructura y márgenes](#6-costes-de-infraestructura-y-márgenes)
7. [Proceso de onboarding de un cliente](#7-proceso-de-onboarding-de-un-cliente)
8. [Argumentario de ventas](#8-argumentario-de-ventas)

---

## 1. Propuesta de valor

### El problema que resuelve

Las empresas manejan miles de documentos no estructurados (facturas, contratos, informes) de los que necesitan extraer datos concretos para introducirlos en sus sistemas (ERP, CRM, Excel). Este proceso hoy lo hacen:

- **Manualmente:** un empleado lee y teclea. Coste: 3-8 minutos por documento.
- **Con OCR básico:** extrae texto, pero no entiende ni clasifica. Requiere programación a medida.
- **Con RPA:** frágil, caro de mantener, falla con variaciones de formato.

### Lo que ofrece Centinell

> Extracción de datos estructurados de cualquier documento, en segundos, sin programación, con precisión del 90-97%, completamente configurable.

**Diferenciadores clave:**
- **Sin código:** el cliente define qué extraer en lenguaje natural. Sin SQL, sin regex.
- **Multi-formato:** PDFs escaneados, Word, texto, imágenes.
- **API-first:** integrable con Power Automate, Zapier, ERP, cualquier sistema en horas.
- **Multi-empresa:** una sola instalación sirve a múltiples clientes aislados.
- **Trazabilidad completa:** auditoría de quién hizo qué, cuándo.

---

## 2. Modelo de negocio

### Dos fuentes de ingresos

```
┌─────────────────────────────────────────────────────────────┐
│  INGRESO 1: Cuota de configuración e integración (one-time) │
│  Se cobra al inicio de cada cliente.                        │
│  Justificación: horas de trabajo, conocimiento, riesgo.     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  INGRESO 2: Cuota mensual por uso (recurring)               │
│  Se cobra mensualmente según tramo de consumo.              │
│  Justificación: infraestructura, soporte, actualizaciónes.  │
└─────────────────────────────────────────────────────────────┘
```

### Por qué este modelo funcióna

- **Para ti:** ingresos recurrentes predecibles + un pago inicial que cubre el trabajo de puesta en marcha.
- **Para el cliente:** convierte un coste fijo y opaco (horas de empleado) en un coste variable y transparente (pago por lo que usa).

---

## 3. Estructura de tarifas

### 3.1 Cuota de configuración e integración (one-time)

| Tipo | Qué incluye | Precio orientativo |
|------|-------------|-------------------|
| **Setup básico** | Creación de BU, hasta 3 plantillas de extracción, alta de usuarios, formación (2h) | **1.500 – 2.500 €** |
| **Integración estándar** | Todo lo anterior + integración API o Power Automate, hasta 6 plantillas, soporte en puesta en marcha (1 mes) | **3.000 – 6.000 €** |
| **Integración avanzada** | Todo lo anterior + OCR configurado para documentos difíciles, múltiples flujos, integración con ERP/CRM, formación extendida (4h), SLA garantizado | **7.000 – 15.000 €** |

**Cuotas adicionales por servicio:**

| Servicio | Precio |
|----------|--------|
| Diseño de nueva plantilla de extracción | 200 – 500 € / plantilla |
| Configuración Power Automate / Zapier | 500 – 1.500 € |
| Integración con ERP específico | 1.000 – 3.000 € |
| Sesión de formación adicional (2h) | 300 – 500 € |
| Auditoría y revisión de extracción existente | 150 – 400 € |

---

### 3.2 Cuota mensual por uso (SaaS)

| Plan | Documentos/mes | Extracciónes/mes | Tokens/mes | Usuarios | Precio/mes |
|------|---------------|-----------------|-----------|---------|-----------|
| **Free** | 50 | 100 | 200.000 | 3 | **0 €** |
| **Starter** | 500 | 1.000 | 2.000.000 | 10 | **49 €** |
| **Professional** | 5.000 | 10.000 | 20.000.000 | 50 | **199 €** |
| **Enterprise** | Ilimitado | Ilimitado | Ilimitado | Ilimitado | **Desde 999 €** |

> **Nota sobre "tokens":** Un token es aproximadamente ¾ de una palabra. Un documento típico de 2 páginas consume entre 2.000 y 5.000 tokens por extracción. El plan Starter cubre ~400-1.000 extracciónes reales según complejidad.

#### Excedentes (overage)

Cuando un cliente supera los límites de su plan:

| Métrica | Precio por unidad adicional |
|---------|---------------------------|
| Documento adicional | 0,10 € / documento |
| Extracción adicional | 0,05 € / extracción |
| Tokens adicionales | 0,003 € / 1.000 tokens |

> **Recomendación:** ofrecer al cliente la opción de subir de plan antes de que incurra en excedentes. Con los datos de `/reports/me` puedes proactivamente avisarle.

---

### 3.3 SLA y soporte (add-on mensual)

| Nivel | Qué incluye | Precio/mes |
|-------|-------------|-----------|
| **Básico** (incluido) | Email, respuesta en 48h | 0 € |
| **Estándar** | Email + chat, respuesta en 8h laborables | 99 €/mes |
| **Premium** | Email + chat + teléfono, respuesta en 2h, 99,5% uptime garantizado | 299 €/mes |

---

## 4. Cómo justificar los honorarios

### 4.1 El coste alternativo del cliente

Este es el argumento más poderoso. Calcula cuánto le cuesta al cliente hacerlo manualmente:

```
Ejemplo: cliente con 500 documentos/mes (plan Starter)

PROCESO MANUAL
  500 documentos × 5 min/doc = 41,7 horas/mes
  A 20 €/hora (coste empresa con SS): 833 €/mes
  + 20% overhead (errores, retrabajo, supervisión): 1.000 €/mes reales

CON CENTINELL STARTER
  Cuota plataforma:       49 €/mes
  Setup 2.000 € / 24 m:  83 €/mes amortizado
  Total:                 132 €/mes

AHORRO MENSUAL:          868 €/mes  (~870 €)

PRIMER AÑO
  Inversión total:       2.588 € (setup + 12 cuotas)
  Ahorro total:         12.000 € (1.000 €/mes × 12)
  Beneficio neto:        9.412 €
  ROI año 1:              364 %

PAYBACK DEL SETUP
  2.000 € setup / 868 € ahorro/mes = 2,3 meses
  → La inversión inicial se recupera en menos de 3 meses.
```

> **El argumento más impactante no es el porcentaje de ROI, sino el payback: el cliente recupera la inversión del setup en 2-3 meses. A partir del mes 4, cada mes ahorra ~870 € netos.**

### 4.2 Qué justifica la cuota de configuración

**"¿Por qué pago 3.000 € de entrada si es un software?"**

Explicación clara para el cliente:

> "La cuota de configuración cubre el tiempo real que invertimos en entender tu negocio, diseñar las plantillas de extracción específicas para tus documentos, integrarlo con tus sistemas y asegurarnos de que funcióna correctamente antes de entregarlo. No es un software genérico que instalas y ya está — es un sistema configurado para tus documentos concretos, con tus campos exactos."

**Desglose honesto de horas para un setup estándar:**

| Actividad | Horas |
|-----------|-------|
| Análisis de documentos del cliente y definición de campos | 4-6h |
| Diseño y prueba de plantillas de extracción | 6-10h |
| Configuración del sistema (BU, usuarios, permisos) | 2-3h |
| Integración con Power Automate o API | 4-8h |
| Pruebas con documentos reales del cliente | 3-5h |
| Formación y documentación para el cliente | 2-4h |
| **Total** | **21-36 horas** |

A una tarifa de 75-120 €/hora, son 1.575 – 4.320 €. El precio es coherente.

### 4.3 Qué justifica la cuota mensual

**"¿Por qué pago si el software ya está instalado?"**

> "La cuota mensual cubre: el coste de los servidores y base de datos donde corren tus datos, el coste de las llamadas a la IA de OpenAI que procesa tus documentos, las actualizaciónes continuas de seguridad y funciónalidad, y el soporte cuando lo necesitas. No es una cuota de licencia por usar un software — es un servicio gestiónado activo."

**Desglose de costes reales que cubre la cuota** (ver sección 6).

---

## 5. Cómo monitorear y controlar el uso

### 5.1 Panel administrativo (tú)

#### Vista global — todas tus cuentas de un vistazo
```
GET /reports/admin/overview
```
Te muestra para el mes en curso:
- Cuántos documentos ha procesado cada cliente
- Cuántas extracciónes ha hecho
- Cuántos tokens ha consumido (= coste directo para ti)
- Qué plan tiene asignado
- Cuántos usuarios activos

**Cuándo mirarlo:** al menos una vez a la semana. Especialmente útil el día 25 de cada mes para anticipar facturas.

#### Detalle de un cliente específico
```
GET /reports/admin/bu/{bu_id}
```
Muestra tendencia día a día de los últimos 30 días, comparativa mes anterior vs. mes actual, y estado de cuotas.

#### Señales de alerta que debes vigilar:

| Señal | Acción |
|-------|--------|
| Cliente al 80%+ de su cuota | Contactarle para subir de plan (oportunidad de upsell) |
| Cliente con 0 actividad en 2 semanas | Contactarle para ver si tiene problemas (riesgo de churn) |
| Tokens consumidos muy altos vs extracciónes | Sus documentos son muy largos o hay un prompt mal configurado |
| Muchas extracciónes fallidas | Problema técnico — revisar configuración de prompt |

### 5.2 Metabase (analytics visual)

Con Metabase conectado a tu base de datos (ver `docker compose --profile analytics up`), puedes crear dashboards permanentes sin escribir código:

**Dashboards recomendados a configurar:**

1. **Dashboard comercial mensual**
   - Ingresos recurrentes proyectados por plan
   - Clientes ordenados por consumo
   - Tendencia de crecimiento mes a mes

2. **Dashboard de costes**
   - Tokens consumidos por cliente (= coste OpenAI)
   - Margen por cliente (precio plan - coste tokens - coste infra)
   - Alertas de clientes que consumen más de lo que pagan

3. **Dashboard de salud**
   - Extracciónes exitosas vs. fallidas
   - Tiempo de respuesta del LLM (latency_ms)
   - Documentos en estado "pending" por más de 10 minutos

### 5.3 Informes para el cliente (bu_admin)

Los propios clientes pueden ver su consumo en:
```
GET /reports/me
```

Esto les da:
- Uso del mes actual vs. límites de su plan (barra de progreso de cuota)
- Comparativa con el mes anterior
- Tendencia diaria de los últimos 30 días

**Beneficio comercial:** el cliente ve en tiempo real cuánto usa, lo que facilita la conversación de upgrade cuando se acerca al límite.

### 5.4 Auditoría y trazabilidad

Todo queda registrado en `audit_events`:
- Quién inició sesión y cuándo
- Quién subió cada documento
- Quién ejecutó cada extracción
- Quién borró qué
- Intentos de acceso denegados

```
GET /admin/audit-events?bu_id=uuid&event_type=extraction.run
```

Esto es valioso para el cliente (cumplimiento, auditoría interna) y para ti (en caso de disputas sobre uso o facturación).

---

## 6. Costes de infraestructura y márgenes

### 6.1 Costes fijos mensuales (tu infraestructura)

| Servicio | Coste estimado/mes |
|----------|-------------------|
| Fly.io (app + volumen 5GB) | 15 – 25 € |
| Supabase (base de datos) | 0 € (free tier hasta 500 MB) → 25 € (pro) |
| Dominio | ~1 € |
| **Total fijo** | **~17 – 51 €/mes** |

### 6.2 Costes variables (OpenAI — por cliente)

Precios OpenAI GPT-4o (Mayo 2026):
- Input: $2,50 / 1M tokens
- Output: $10,00 / 1M tokens
- Mix típico (80% input, 20% output): ~$3,80 / 1M tokens

**Coste por plan:**

| Plan | Tokens/mes | Coste OpenAI/mes | Precio plan | Margen bruto |
|------|-----------|-----------------|------------|-------------|
| Free | 200.000 | ~0,76 € | 0 € | **−0,76 €** |
| Starter | 2.000.000 | ~7,60 € | 49 € | **~38 €** (78%) |
| Professional | 20.000.000 | ~76 € | 199 € | **~110 €** (55%) |
| Enterprise | — | ~400 € (est.) | 999 € | **~500 €** (50%) |

> **Nota importante:** los planes `free` son un coste. Úsalos solo como trial limitado y convierte rápido al cliente en `starter`.

### 6.3 Margen total proyectado

**Escenario conservador: 10 clientes activos**

| Mix de clientes | Ingresos/mes | Costes OpenAI | Costes fijos | **Margen neto** |
|-----------------|-------------|--------------|-------------|----------------|
| 2 free + 5 starter + 2 professional + 1 enterprise | 245 + 398 + 999 = **1.642 €** | ~238 € | ~50 € | **~1.354 €** |

**Escenario realista: 20 clientes**

| Mix | Ingresos/mes | Costes | **Margen neto** |
|-----|-------------|--------|----------------|
| 3 free + 10 starter + 5 professional + 2 enterprise | 490 + 995 + 1.998 = **3.483 €** | ~650 € | **~2.800 €** |

> A esto suma: 2-4 setups nuevos/mes = **3.000 – 12.000 € adicionales** por configuraciónes.

---

## 7. Proceso de onboarding de un cliente

### Paso a paso

#### 1. Firma de contrato / inicio de proyecto
- Firmar acuerdo de servicio con precio de setup y plan mensual elegido
- Recibir muestra de documentos reales del cliente (5-10 ejemplos)

#### 2. Análisis de documentos (1-2 días)
- Revisar qué campos necesita extraer el cliente
- Identificar variabilidad de formato (¿todos los documentos son iguales? ¿hay versiónes?)
- Definir plantilla de variables

#### 3. Configuración técnica (1 día)
Desde el panel de Centinell como admin_global:
```
1. POST /bus/          — Crear BU del cliente (código único, ej. ACME)
2. POST /admin/users   — Crear usuario bu_admin del cliente
3. POST /bus/{id}/users — Asignar usuario a la BU
4. PUT /reports/admin/bu/{id}/plan — Asignar plan contratado
```

#### 4. Diseño de plantillas (2-5 días)
- Crear PromptConfigs para cada tipo de documento
- Probar con documentos reales del cliente
- Ajustar hasta obtener precisión >90%

#### 5. Integración (1-3 días)
- Si API: proporcionar documentación + API key de prueba
- Si Power Automate: configurar el flujo y probarlo extremo a extremo

#### 6. Formación y entrega
- Sesión de formación con los usuarios del cliente (2h)
- Entrega de documentación específica
- Periodo de soporte intensivo (2 semanas)

#### 7. Seguimiento mensual
- Revisar métricas de uso con el cliente
- Identificar oportunidades de mejora o nuevas plantillas
- Renovación/upgrade de plan si aplica

---

## 8. Argumentario de ventas

### Objeción: "Es muy caro"
> "Calculemos juntos cuántas horas invierte tu equipo al mes en introducir datos de documentos. Si son más de 10 horas, Centinell se paga solo desde el primer mes."

### Objeción: "¿Y si el AI se equivoca?"
> "Centinell incluye el campo `source_quote` que muestra exactamente de qué parte del documento viene cada dato. Tus usuarios pueden verificar cualquier resultado en segundos. Es más rápido revisar lo que extrae la IA que introducirlo todo a mano."

### Objeción: "¿Mis datos están seguros?"
> "Tus datos se almacenan en una base de datos exclusiva para tu empresa, completamente aislada de otros clientes. Todo acceso queda registrado en auditoría. Los documentos se eliminan cuando tú lo decides. OpenAI procesa el texto pero no almacena los datos de los documentos."

### Objeción: "¿Puedo integrarlo con nuestro ERP?"
> "Sí. Centinell tiene una API REST completa con autenticación por API Key. Si vuestro ERP puede hacer llamadas HTTP (y casi todos pueden), la integración es directa. También funcióna con Power Automate y Zapier sin escribir código."

### Objeción: "¿Qué pasa si crecemos mucho?"
> "Los planes escalan automáticamente. Cuando vuestro consumo se acerque al límite, os avisamos antes de que lleguéis. Cambiar de plan es inmediato, sin cambios técnicos de tu parte."

### Propuesta de valor resumida en una frase

> **"Centinell convierte pilas de documentos en datos estructurados en segundos, integrable con cualquier sistema, sin necesidad de programadores."**

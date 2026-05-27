# Centinell — Especificación Funciónal Completa
**Versión:** 1.0 | **Fecha:** Mayo 2026

---

## Índice

1. [Qué es Centinell](#1-qué-es-centinell)
2. [Modelo de multi-tenancy (BUs)](#2-modelo-de-multi-tenancy-bus)
3. [Roles y permisos](#3-roles-y-permisos)
4. [Autenticación](#4-autenticación)
5. [Módulos funciónales](#5-módulos-funciónales)
6. [Referencia completa de API](#6-referencia-completa-de-api)
7. [Modelo de datos](#7-modelo-de-datos)
8. [Seguridad](#8-seguridad)
9. [Infraestructura y despliegue](#9-infraestructura-y-despliegue)

---

## 1. Qué es Centinell

Centinell es una plataforma SaaS de **inteligencia documental**. Recibe documentos (PDF, Word, texto plano, imágenes escaneadas), extrae texto estructurado mediante OCR y procesamiento de IA (GPT-4o), y devuelve los campos solicitados en formato JSON exportable a Excel/CSV.

### Casos de uso principales

| Sector | Ejemplo de uso |
|--------|----------------|
| Jurídico / Legal | Extraer partes, fechas, cláusulas clave de contratos |
| Seguros | Extraer datos de siniestros, pólizas, informes periciales |
| Contabilidad / Fiscal | Extraer importes, NIF, fechas de facturas |
| RRHH | Extraer candidatos, experiencia, formación de CVs |
| Inmobiliario | Extraer superficies, cargas, linderos de escrituras |
| Sanidad | Extraer diagnósticos, medicaciones de informes clínicos |

### Qué NO es Centinell

- No es un sistema de gestión documental (DMS). No almacena documentos a largo plazo.
- No es un motor OCR propio. Usa Tesseract (gratuito) y opcionalmente GPT-4o Vision.
- No tiene flujos de aprobación ni firma electrónica.

---

## 2. Modelo de multi-tenancy (BUs)

Centinell está diseñado para servir a **múltiples clientes completamente aislados** dentro de la misma instalación.

Cada cliente es una **Business Unit (BU)**:
- Tiene su propio código único (ej. `ACME`)
- Sus documentos, extracciónes, colecciónes y configuraciónes son **completamente privados**
- Ningún usuario de la BU `ACME` puede ver ni acceder a datos de la BU `BETA`
- El aislamiento se aplica en la capa de base de datos mediante `bu_id` en todas las tablas

```
┌─────────────────────────────────────────────────────┐
│                   admin_global                       │
│           ve y gestióna todas las BUs               │
└──────────────────────┬──────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
   ┌────▼────┐    ┌────▼────┐   ┌────▼────┐
   │  BU:    │    │  BU:    │   │  BU:    │
   │  ACME   │    │  BETA   │   │  GAMMA  │
   │         │    │         │   │         │
   │ usuarios│    │ usuarios│   │ usuarios│
   │ docs    │    │ docs    │   │ docs    │
   │ extracs │    │ extracs │   │ extracs │
   └─────────┘    └─────────┘   └─────────┘
```

---

## 3. Roles y permisos

### Jerarquía de roles

```
admin_global  >  bu_admin  >  bu_user  >  bu_viewer
```

| Acción | admin_global | bu_admin | bu_user | bu_viewer |
|--------|:---:|:---:|:---:|:---:|
| Ver documentos | ✅ | ✅ | ✅ | ✅ |
| Subir documentos | ✅ | ✅ | ✅ | ❌ |
| Borrar documentos | ✅ | ✅ | ✅ | ❌ |
| Ejecutar extracciónes | ✅ | ✅ | ❌ | ❌ |
| Ver historial extracciónes | ✅ | ✅ | ❌ | ❌ |
| Ver evaluaciónes | ✅ | ✅ | ❌ | ❌ |
| Ver colecciónes | ✅ | ✅ | ✅ | ✅ |
| Crear colecciónes | ✅ | ✅ | ✅ | ❌ |
| Exportar colecciónes | ✅ | ✅ | ✅ | ❌ |
| Gestiónar usuarios BU | ✅ | ✅ | ❌ | ❌ |
| Crear/editar prompts | ✅ | ✅ | ❌ | ❌ |
| Crear API Keys | ✅ | ✅ | ❌ | ❌ |
| Ver informes de uso | ✅ | ✅ | ❌ | ❌ |
| Gestiónar todas las BUs | ✅ | ❌ | ❌ | ❌ |
| Gestiónar planes | ✅ | ❌ | ❌ | ❌ |
| Ver auditoría global | ✅ | ❌ | ❌ | ❌ |

### Notas de roles

- **admin_global**: creado en bootstrap (`.env`), no pertenece a ninguna BU, ve todo.
- **bu_admin**: administrador de su BU. Crea usuarios, configura prompts, ve métricas.
- **bu_user**: usuario operativo. Sube documentos pero no puede ejecutar extracciónes directamente (acceso vía API key programática o proceso batch).
- **bu_viewer**: solo lectura.

---

## 4. Autenticación

Centinell soporta dos mecanismos de autenticación:

### 4.1 JWT con cookies httpOnly (frontend / interactivo)

1. El usuario hace `POST /auth/login` con email y contraseña.
2. El servidor valida credenciales y devuelve:
   - Cookie `centinell_access` (JWT, httpOnly, 15 min) — para todas las requests
   - Cookie `centinell_refresh` (token opaco, httpOnly, 7 días) — solo para `/auth/refresh`
3. Los tokens **nunca aparecen en el body** ni en localStorage. Protección XSS automática.
4. El refresh token se **rota** en cada uso: el anterior queda revocado en BD inmediatamente.

### 4.2 API Keys (integración programática / Power Automate)

- Formato: `cnt_<32 caracteres random>` — ej. `cnt_abc123...`
- Se pasa en la cabecera `X-API-Key`
- Asociada a una BU y un rol concreto
- Se pueden crear y revocar desde el panel (bu_admin)
- `last_used_at` se actualiza en cada uso para auditoría

### 4.3 Cabecera X-BU-ID

Todas las requests que operan sobre recursos de una BU requieren la cabecera:
```
X-BU-ID: <uuid-de-la-bu>
```
Esto permite que un `admin_global` opere en cualquier BU cambiando esta cabecera.
Las API Keys no necesitan esta cabecera (la BU está embebida en la key).

---

## 5. Módulos funciónales

### 5.1 Gestión de documentos

**Flujo de un documento:**
```
Upload → Almacenamiento local → OCR en background → status: processed
                                        ↓
                               Texto disponible para extracción
```

**Formatos soportados:**
- PDF (con texto nativo, con imágenes, mixtos)
- Word (.docx)
- Texto plano (.txt, .md, .json, .csv, .xml, .html)

**Pipeline OCR (para PDFs):**
1. Extracción de texto nativo página a página (pypdf)
2. Detección de imágenes embebidas
3. Si hay imágenes o texto pobre: OCR con Tesseract (configurable) o GPT-4o Vision
4. Comparación de calidad por página → se elige la mejor fuente

**Campos del documento:**
```
id, bu_id, title, filename, mime_type, size_bytes, sha256,
storage_key, created_by, created_at, status, ocr_text, ocr_error
```

**Estados del documento:**
- `pending` — recién subido, OCR no iniciado
- `processing` — OCR en curso
- `processed` — texto extraído, listo para extracción
- `failed` — OCR fallido (ver campo `ocr_error`)

### 5.2 Configuraciónes de prompt (plantillas de extracción)

Una **PromptConfig** define qué campos extraer de un documento. Es la "plantilla" del extractor.

**Ejemplo de configuración:**
```json
{
  "name": "Extractor de facturas",
  "base_prompt": "Extrae los siguientes campos del documento: {{VARIABLE_BLOCK}}",
  "model": "gpt-4o",
  "temperature": 0,
  "variables": [
    { "name": "numero_factura", "description": "Número de factura", "type": "string", "required": true },
    { "name": "fecha_emision",  "description": "Fecha de emisión (YYYY-MM-DD)", "type": "date",   "required": true },
    { "name": "importe_total",  "description": "Importe total con IVA en euros", "type": "number", "required": true },
    { "name": "nif_proveedor",  "description": "NIF o CIF del emisor", "type": "string", "required": false }
  ]
}
```

El sistema construye automáticamente el prompt final insertando las variables. Soporta **dependencias entre variables** (`{{NombreVar}}` en la descripción de otra variable).

### 5.3 Extracciónes

Una extracción es la ejecución de un PromptConfig sobre un documento.

**Flujo asíncrono:**
```
POST /extract/  →  Crea registro pending  →  Devuelve extraction_id
                          ↓
                   Background task: llama al LLM
                          ↓
              GET /extractions/{id}  →  status: success / failed
```

**El resultado incluye:**
- Cada campo extraído con `title`, `answer`, `reasoning` y `source_quote`
- Métricas de coste: `prompt_tokens`, `completion_tokens`, `latency_ms`

**Retry logic:** hasta 3 intentos con backoff exponencial en errores 429/5xx.

**Validación humana:** una extracción puede marcarse como `validated` con resultado corregido manualmente.

### 5.4 Colecciónes (proceso en lote)

Una colección agrupa múltiples extracciónes del mismo tipo (mismo PromptConfig).

**Caso de uso:** procesar un lote de 500 facturas del mismo proveedor con la misma plantilla.

- Muestra conteos: `total_docs`, `success_count`, `failed_count`, `validated_count`
- Exportación a Excel en un clic: cada fila = documento, cada columna = campo extraído

### 5.5 Evaluaciónes (Assessments)

Las evaluaciónes permiten ejecutar **múltiples PromptConfigs secuencialmente** sobre un mismo documento y combinar los resultados.

**Caso de uso:** un contrato que necesita tres extractores distintos (partes, cláusulas económicas, cláusulas de rescisión) ejecutados en orden.

- Los configs se ordenan por `position`
- El resultado combinado se consolida en `combined_result`
- Historial completo de ejecuciones en `assessment_runs`

### 5.6 Tracking de uso y planes

Cada operación significativa genera un **evento de uso** en la tabla `usage_events`:

| Evento | Cuándo se genera | Quantity |
|--------|-----------------|---------|
| `doc.uploaded` | Al subir un documento | 1 |
| `doc.deleted` | Al borrar un documento | 1 |
| `extraction.run` | Al completar/fallar una extracción | 1 |
| `tokens.consumed` | Al completar una extracción con éxito | N tokens |
| `collection.export` | Al descargar un Excel de colección | 1 |

Los eventos son **append-only**: nunca se modifican ni borran. Son la fuente de verdad para facturación y auditoría.

**Planes disponibles:**

| Código | Nombre | Docs/mes | Extracciónes | Tokens/mes | Usuarios | Precio |
|--------|--------|----------|-------------|-----------|---------|--------|
| `free` | Gratuito | 50 | 100 | 200.000 | 3 | 0 € |
| `starter` | Starter | 500 | 1.000 | 2.000.000 | 10 | 49 €/mes |
| `professional` | Professional | 5.000 | 10.000 | 20.000.000 | 50 | 199 €/mes |
| `enterprise` | Enterprise | ∞ | ∞ | ∞ | ∞ | 999 €/mes |

---

## 6. Referencia completa de API

**Base URL:** `https://tu-dominio.com` (local: `http://localhost:8000`)
**Documentación interactiva:** `/api/docs`

**Autenticación en todas las llamadas:**
- Opción A: Cookie `centinell_access` (automática en browser)
- Opción B: Header `Authorization: Bearer <jwt>`
- Opción C: Header `X-API-Key: cnt_...`

Recursos de BU también requieren: `X-BU-ID: <uuid>`

---

### AUTH — Autenticación

#### `POST /auth/login`
Inicia sesión y establece cookies httpOnly.
```json
// Request
{ "email": "user@empresa.com", "password": "contraseña" }

// Response 200
{
  "expires_in": 900,
  "user": { "id": "uuid", "email": "...", "full_name": "...", "role": "bu_admin" }
}
// + Cookies: centinell_access, centinell_refresh
```
| Código | Significado |
|--------|-------------|
| 200 | OK — cookies establecidas |
| 401 | Credenciales inválidas |
| 403 | Sin BU asignada o BU inactiva |

#### `POST /auth/refresh`
Rota el refresh token y emite nuevos tokens.
```json
// Request (body solo necesario si no hay cookie)
{ "refresh_token": "token-opaco-opcional" }
// Response: mismo formato que /login
```

#### `POST /auth/logout`
Limpia las cookies de sesión. No requiere body. Respuesta 204.

---

### BUSINESS UNITS — Gestión de clientes

#### `GET /bus/my-access`
Lista las BUs a las que tiene acceso el usuario autenticado.
```json
// Response 200
[{ "id": "uuid", "name": "Empresa Acme", "code": "ACME", "is_active": true, "created_at": "..." }]
```

#### `GET /bus/` ⚠️ admin_global
Lista todas las BUs del sistema.

#### `POST /bus/` ⚠️ admin_global
Crea una nueva BU (nuevo cliente).
```json
{ "name": "Empresa Acme", "code": "ACME" }
```

#### `POST /bus/{bu_id}/users` ⚠️ bu_admin
Asigna un usuario a la BU con un rol.
```json
{ "user_id": "uuid", "role": "bu_user" }
// Roles válidos: bu_admin | bu_user | bu_viewer
```

#### `GET /bus/{bu_id}/users` ⚠️ bu_admin
Lista usuarios con acceso a la BU.

#### `DELETE /bus/{bu_id}/users/{user_id}` ⚠️ bu_admin
Revoca el acceso de un usuario a la BU. Respuesta 204.

---

### DOCUMENTOS

#### `POST /documents/` ⚠️ bu_user+
Sube un documento. Inicia OCR en background.
```
Content-Type: multipart/form-data
file: <archivo>
Headers: X-BU-ID: <uuid>

// Response 201
{
  "id": "uuid", "bu_id": "uuid", "filename": "factura.pdf",
  "status": "pending", "created_at": "...", "size_bytes": 45000
}
```

#### `POST /documents/from-base64` ⚠️ bu_user+
Sube un documento en Base64 (para integraciónes API/Power Automate).
```json
{ "filename": "factura.pdf", "content_base64": "JVBERi0xLjQ..." }
```

#### `GET /documents/`
Lista documentos de la BU con paginación.
```
?limit=20&offset=0
// Response: { "items": [...], "total": 234 }
```

#### `GET /documents/{id}`
Detalle de un documento (incluye `ocr_text` si ya procesado).

#### `DELETE /documents/{id}` ⚠️ bu_user+
Elimina un documento y su archivo físico. Respuesta 204.

#### `GET /documents/{id}/download`
Descarga el archivo original.

#### `POST /documents/parse`
Extrae texto de un archivo sin almacenarlo. Útil para preview antes de extracción.
```json
// Response
{ "text": "...", "char_count": 4500, "used_ocr": true, "ocr_warning": null }
```

#### `GET /documents/{id}/runs`
Lista extracciónes simples del documento.

#### `GET /documents/{id}/assessment-runs`
Lista ejecuciones de evaluación del documento.
```
?limit=20&offset=0
```

---

### CONFIGURACIONES DE PROMPT

#### `GET /prompt-configs/`
Lista configuraciónes activas de la BU.

#### `POST /prompt-configs/` ⚠️ bu_admin
Crea una nueva plantilla de extracción.
```json
{
  "name": "Extractor de contratos",
  "description": "...",
  "base_prompt": "Extrae {{VARIABLE_BLOCK}}",
  "model": "gpt-4o",
  "temperature": 0,
  "variables": [
    { "name": "campo", "description": "Descripción", "type": "string", "required": true }
  ]
}
```

#### `GET /prompt-configs/{id}`
Detalle de una configuración.

#### `PUT /prompt-configs/{id}` ⚠️ bu_admin
Actualiza una configuración (crea nueva versión).

#### `DELETE /prompt-configs/{id}` ⚠️ bu_admin
Desactiva una configuración.

---

### EXTRACCIONES

#### `POST /extract/` ⚠️ bu_admin+
Lanza una extracción asíncrona.
```json
{
  "config_id": "uuid",
  "document_text": "Texto del documento...",
  "document_name": "factura_enero.pdf",
  "document_id": "uuid-opcional",
  "collection_id": "uuid-opcional"
}
// Response 200 (inmediato)
{ "extraction_id": "uuid", "config_id": "uuid", "result": [] }
// Sondear GET /extractions/{extraction_id} hasta status != "pending"
```

#### `GET /extractions/`
Historial de extracciónes de la BU.
```
?config_id=uuid&document_id=uuid&status=success|failed|validated&limit=50
```

#### `GET /extractions/{id}`
Detalle de una extracción (incluye `validated_result`, `raw_llm_response`, `prompt_sent`).
```json
{
  "id": "uuid", "status": "success",
  "validated_result": [
    { "title": "numero_factura", "answer": "F-2024-0123", "reasoning": "...", "source_quote": "..." }
  ],
  "latency_ms": 2340, "model_used": "gpt-4o"
}
```

#### `PATCH /extractions/{id}/validate` ⚠️ bu_user+
Guarda la revisión humana de una extracción.
```json
{ "result": [{ "title": "campo", "answer": "valor corregido" }] }
```

#### `GET /extractions/{id}/export/xlsx`
Exporta una extracción como Excel (2 columnas: Campo | Valor).

#### `GET /extractions/export/bulk`
Exportación masiva en CSV, XLSX o JSON.
```
?format=csv|xlsx|json&config_id=uuid&collection_id=uuid&status=success&limit=200
```

---

### COLECCIONES

#### `GET /collections/`
Lista colecciónes de la BU con conteos de extracciónes.
```json
[{
  "id": "uuid", "name": "Facturas Enero", "config_id": "uuid",
  "total_docs": 145, "success_count": 143, "failed_count": 2, "validated_count": 12
}]
```

#### `POST /collections/` ⚠️ bu_user+
Crea una nueva colección.
```json
{ "name": "Facturas Enero 2024", "config_id": "uuid" }
```

#### `GET /collections/{id}`
Detalle de una colección con conteos.

#### `GET /collections/{id}/extractions`
Lista todas las extracciónes de la colección.

#### `GET /collections/{id}/export/xlsx`
Descarga Excel completo de la colección.
_(Cada fila = documento. Cada columna = campo extraído. Formato dinámico)_

---

### API KEYS

#### `GET /api-keys/` ⚠️ bu_admin
Lista API Keys activas de la BU.

#### `POST /api-keys/` ⚠️ bu_admin
Crea una nueva API Key. La clave completa **solo se muestra una vez**.
```json
{ "name": "Power Automate Prod", "role": "bu_user" }
// Response
{ "id": "uuid", "key": "cnt_abc123...", "key_prefix": "cnt_abc123", "role": "bu_user" }
```

#### `DELETE /api-keys/{id}` ⚠️ bu_admin
Revoca una API Key. Respuesta 204.

---

### INFORMES Y PLANES

#### `GET /plans`
Lista planes del catálogo (público, sin autenticación).

#### `POST /plans` ⚠️ admin_global
Crea un plan personalizado.

#### `PATCH /plans/{id}` ⚠️ admin_global
Modifica límites o precio de un plan.

#### `GET /reports/me` ⚠️ bu_admin
Resumen de uso de la BU activa: mes actual, mes anterior, tendencia 30 días, estado de cuotas.
```json
{
  "bu_name": "Empresa Acme", "plan": { "display_name": "Starter", ... },
  "quota_status": { "extractions_used": 450, "extractions_limit": 1000, "extractions_pct": 45.0 },
  "current_month": { "docs_uploaded": 89, "extractions_run": 450, "tokens_consumed": 890000 },
  "daily_trend": [{ "date": "2026-05-01", "docs_uploaded": 5, "extractions_run": 22, "tokens_consumed": 44000 }]
}
```

#### `GET /reports/admin/overview` ⚠️ admin_global
Vista ejecutiva de todas las BUs con su consumo del mes.

#### `GET /reports/admin/bu/{bu_id}` ⚠️ admin_global
Detalle completo de cualquier BU.

#### `PUT /reports/admin/bu/{bu_id}/plan` ⚠️ admin_global
Asigna un plan a una BU.
```json
{ "plan_id": "uuid-del-plan" }
```

---

### ADMIN (gestión interna)

#### `GET /admin/dashboard` ⚠️ admin_global
Métricas globales: usuarios, BUs, extracciónes totales, fallos últimas 24h.

#### `GET /admin/audit-events` ⚠️ admin_global
Log de auditoría completo con filtros.
```
?event_type=auth.login&actor_user_id=uuid&bu_id=uuid&skip=0&limit=100
```

#### `GET /admin/users` ⚠️ admin_global
Lista todos los usuarios del sistema.

#### `POST /admin/users` ⚠️ admin_global
Crea un usuario nuevo.
```json
{ "email": "user@empresa.com", "full_name": "Nombre", "password": "pass", "is_global_admin": false }
```

---

## 7. Modelo de datos

### Tablas principales

```
business_units          users                   user_bu_access
──────────────          ─────                   ──────────────
id (PK)                 id (PK)                 id (PK)
name                    email (UNIQUE)          user_id → users
code (UNIQUE)           full_name               bu_id → business_units
is_active               password_hash           role
created_at              is_global_admin         is_active
                        is_active               created_at
                        created_at
                        last_login_at

documents               prompt_configs          extractions
─────────               ──────────────          ───────────
id (PK)                 id (PK)                 id (PK)
bu_id → bus             bu_id → bus             prompt_config_id → pconfigs
title                   name                    bu_id → buses
filename                description             document_id → documents
mime_type               base_prompt             collection_id → collections
size_bytes              variables (JSON)        document_name
sha256                  model                   document_hash
storage_key             temperature             prompt_sent
created_by → users      is_active               raw_llm_response
created_at              created_at              validated_result (JSON)
status                  updated_at              status
ocr_text                                        retries
ocr_error                                       latency_ms
                                                model_used
                                                error_message
                                                created_at

collections             assessments             assessment_runs
───────────             ───────────             ───────────────
id (PK)                 id (PK)                 id (PK)
bu_id → buses           bu_id → buses           assessment_id
name                    name                    assessment_name
config_id → pconfigs    description             bu_id
created_at              is_active               document_id
                        created_at              document_name
                        updated_at              created_by → users
                                                status
assessment_configs      api_keys                combined_result (JSON)
──────────────────      ────────                error_message
id (PK)                 id (PK)                 latency_ms
assessment_id           bu_id → buses           created_at
config_id               created_by → users      updated_at
position                name
                        key_prefix
                        key_hash (SHA-256)      refresh_tokens
                        role                    ──────────────
                        is_active               id (PK)
                        created_at              user_id → users
                        last_used_at            token_hash
                                                expires_at
audit_events            usage_events            revoked_at
────────────            ────────────            created_at
id (PK)                 id (PK)
actor_user_id           bu_id → buses
bu_id                   user_id → users         plans
event_type              event_type              ─────
resource_type           quantity                id (PK)
resource_id             metadata (JSON)         code (UNIQUE)
message                 created_at              display_name
metadata (JSON)                                 max_docs_per_month
created_at              bu_plans                max_extractions_per_month
                        ────────                max_tokens_per_month
                        id (PK)                 max_users
                        bu_id → buses           price_monthly_cents
                        plan_id → plans         is_active
                        starts_at               created_at
                        ends_at (NULL=activo)
                        created_by → users
                        created_at
```

---

## 8. Seguridad

### Medidas implementadas

| Área | Implementación |
|------|---------------|
| Autenticación | JWT HS256 + httpOnly cookies. Tokens nunca en localStorage |
| Refresh tokens | Rotación estricta. Un token solo usable una vez. Revocación en BD |
| Contraseñas | bcrypt con salt (bcrypt.hashpw) |
| API Keys | SHA-256 del secreto almacenado. La clave en claro solo se muestra al crear |
| Aislamiento de datos | `bu_id` en todas las queries. Sin cross-BU posible a nivel de API |
| Auditoría | Tabla `audit_events` con actor, BU, acción, recurso y timestamp |
| Headers de seguridad | `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, HSTS |
| CORS | Orígenes explícitos vía `CORS_ORIGINS` env. Vacío = mismo origen |
| Sesiones | Estado de refresh tokens en BD (no en JWT) → revocación inmediata posible |

### Variables de entorno críticas

```bash
JWT_SECRET_KEY=<256-bit random>       # Nunca en código
OPENAI_API_KEY=<sk-...>               # Solo en .env, nunca en repositorio
BOOTSTRAP_ADMIN_PASSWORD=<segura>     # Solo en primer bootstrap
DATABASE_URL=postgresql+asyncpg://... # Credenciales de BD
```

---

## 9. Infraestructura y despliegue

### Stack técnico

| Componente | Tecnología |
|-----------|-----------|
| Backend | Python 3.11 / FastAPI / SQLAlchemy async |
| Base de datos | PostgreSQL (Supabase en producción) |
| ORM / Migraciones | SQLAlchemy 2.0 + Alembic |
| LLM | OpenAI GPT-4o via API |
| OCR | Tesseract + Poppler (opcional) / GPT-4o Vision (opcional) |
| Frontend | HTML + CSS + Vanilla JS (SPA embebida) |
| Servidor HTTP | Uvicorn (ASGI) |
| Despliegue | Fly.io (región Amsterdam) |
| Almacenamiento | Volumen persistente Fly.io (5 GB) |
| Analytics | Metabase (opcional, docker compose) |

### Variables de entorno principales

```bash
DATABASE_URL                    # Conexión PostgreSQL
OPENAI_API_KEY                  # Clave API de OpenAI
JWT_SECRET_KEY                  # Secreto para firmar JWTs
BOOTSTRAP_ADMIN_EMAIL           # Email del admin inicial
BOOTSTRAP_ADMIN_PASSWORD        # Contraseña del admin inicial
ACCESS_TOKEN_EXPIRE_MINUTES     # Default: 15
REFRESH_TOKEN_EXPIRE_MINUTES    # Default: 10080 (7 días)
MAX_DOCUMENT_SIZE_MB            # Default: 5
OCR_FALLBACK_ENABLED            # Default: true
DOCUMENT_STORAGE_DIR            # Default: storage/documents
DEBUG                           # true solo en desarrollo local
```

### Migraciones de base de datos

```bash
# Aplicar todas las migraciones pendientes
alembic upgrade head

# Historial de migraciones
alembic history

# Revertir última migración
alembic downgrade -1
```

**Migraciones disponibles:**
- `0001` — Schema base (todas las tablas core)
- `0002` — Status y OCR text en documentos
- `0003` — API Keys y atribución de runs
- `0004` — `collections.bu_id` directo + `assessment_runs.updated_at`
- `0005` — `usage_events`, `plans`, `bu_plans`

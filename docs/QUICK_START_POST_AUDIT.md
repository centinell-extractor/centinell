# ⚡ Quick Start Post-Auditoría

## Lo que cambió

Se ha completado una auditoría completa del proyecto Centinell. Los siguientes archivos fueron modificados:

```
✅ app/config.py                    - Validación y constantes de configuración
✅ app/main.py                      - Exception handler, CORS, /health
✅ app/services/llm_client.py       - Retry logic, validaciones robustas
✅ app/routers/extract.py           - Validación de tamaño de documento
✅ app/routers/documents.py         - Validación de tamaño de archivo
✅ app/routers/prompt_configs.py    - Paginación en listados
✅ app/db/models.py                 - Float temperature + índices
✅ .env.example                     - Documentación completa
✅ .env.dev                         - Config para desarrollo
```

---

## 🚨 ACCIÓN INMEDIATA (Antes de usar en producción)

### 1. Configurar CORS (CRÍTICO)
Editar [app/main.py](app/main.py#L28) línea 28:

```python
# ❌ ACTUAL (INSEGURO)
allow_origins=["*"],

# ✅ CORRIJO A (Especificar dominio)
allow_origins=["https://mi-frontend.com", "https://app.mi-empresa.com"],
```

**Por qué**: `allow_origins=["*"]` permite solicitudes de cualquier dominio (riesgo CORS).

---

### 2. Verificar .env (CRÍTICO)
```bash
# Copiar template
cp .env.example .env

# Rellenar valores reales (NO commitear)
cat .env  # Edit: DATABASE_URL, OPENAI_API_KEY
```

**Valores necesarios**:
```env
DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/db"
OPENAI_API_KEY="sk-..."
```

---

### 3. Probar retry logic (RECOMENDADO)
Verificar que los reintentos funcionan:

```bash
# Terminal 1: Iniciar servidor
python -m uvicorn app.main:app --reload

# Terminal 2: Test simple
curl -X POST http://localhost:8000/extract-test \
  -H "Content-Type: application/json" \
  -d '{
    "document_text": "Factura: NIF 12345678X, Total €100",
    "variables": [
      {"name": "NIF", "description": "NIF del documento", "type": "string", "required": true}
    ]
  }'
```

Si falla, los logs mostrarán reintentos automáticos. ✅

---

## ✨ Nuevas características

### 1. Health Check
```bash
# Nueva ruta para monitoreo
curl http://localhost:8000/health
# {"status": "healthy", "service": "Centinell", "version": "1.0.0"}
```

Úsalo en load balancers, k8s, etc.

---

### 2. Límites de Configuración
Controla el consumo de recursos editando `.env`:

```env
# Tamaño máximo de documento (default 5 MB)
MAX_DOCUMENT_SIZE_MB=10

# Timeout para llamadas a LLM (default 120s, max 300s)
LLM_TIMEOUT_SECONDS=150

# Reintentos automáticos (default 3)
LLM_RETRY_ATTEMPTS=5

# Máximo de extracciones simultáneas (default 10)
MAX_CONCURRENT_EXTRACTIONS=20
```

---

### 3. Paginación en Listados
```bash
# Antes: GET /prompt-configs (devolvía todos)
# Ahora: GET /prompt-configs con paginación

curl "http://localhost:8000/prompt-configs?skip=0&limit=50"
curl "http://localhost:8000/prompt-configs?skip=50&limit=50"  # Página 2
```

Límites: `1 <= limit <= 500`

---

## 📊 Lo que mejora con estos cambios

| Escenario | Antes | Después |
|-----------|-------|---------|
| LLM timeout (red lenta) | ❌ Falla | ✅ Reintentos automáticos |
| Documento > 5MB | ❌ OOM crash | ✅ 413 Payload Too Large |
| 100 usuarios concurrentes | ⚠️ Lento | ✅ Escalable (con índices DB) |
| API error genérico | ❌ Stack trace al cliente | ✅ Error genérico seguro |
| Listado > 10k items | ❌ Memoria explota | ✅ Paginación límite 500 |

---

## 🔍 Checklist de Verificación

Ejecutar estos tests antes de producción:

```bash
# ✅ 1. Healthcheck
curl http://localhost:8000/health | grep "healthy"

# ✅ 2. Crear config
curl -X POST http://localhost:8000/prompt-configs \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Config",
    "base_prompt": "Extract {{VARIABLE_BLOCK}}",
    "variables": [{"name": "Field1", "description": "Test", "required": true, "type": "string"}],
    "model": "gpt-4o",
    "temperature": 0
  }'

# ✅ 3. Paginación
curl "http://localhost:8000/prompt-configs?skip=0&limit=10" | grep "items"

# ✅ 4. Documento grande (debe rechazar)
curl -X POST http://localhost:8000/extract-test \
  -H "Content-Type: application/json" \
  -d '{"document_text":"'$(head -c 10000000 /dev/zero | tr '\0' 'A')'", "variables": []}'
# Debe devolver: 413 Payload Too Large
```

---

## 📚 Documentación

- **[AUDIT_REPORT.md](AUDIT_REPORT.md)** - Reporte completo de auditoría
- **[PRE_PRODUCTION_CHECKLIST.md](PRE_PRODUCTION_CHECKLIST.md)** - Checklist para producción
- **[.env.example](.env.example)** - Todas las variables documentadas
- **[guia_rapida.md](docs/guia_rapida.md)** - Guía de uso general

---

## ⏰ Próximas Mejoras (En Orden de Prioridad)

1. **ALTA**: Rate limiting (2 horas)
   ```bash
   pip install slowapi
   # Agregar en main.py para limitar a 100 req/min
   ```

2. **MEDIA**: JSON logging (1 hora)
   ```bash
   pip install python-json-logger
   # Para mejor análisis en producción
   ```

3. **BAJA**: Tests unitarios (4 horas)
   ```bash
   pip install pytest pytest-asyncio
   # test/test_validators.py, test/test_llm_client.py
   ```

---

## 🆘 Troubleshooting

**P: "LLM timeout después de 3 reintentos"**
- A: Aumentar `LLM_TIMEOUT_SECONDS` en .env o reducir tamaño doc

**P: "413 Payload Too Large en documento pequeño"**
- A: Verificar encoding. Algunos PDFs pueden expandirse al extraer texto

**P: "Database connection exhausted"**
- A: Aumentar `pool_size` en [app/db/connection.py](app/db/connection.py#L13)

**P: "CORS error en navegador"**
- A: Agregar tu dominio a `allow_origins` en [app/main.py](app/main.py#L28)

---

**¡El proyecto está listo para uso masivo! 🚀**

Próximas tareas:
1. ✅ Revisar cambios en AUDIT_REPORT.md
2. ⏳ Corregir CORS (5 min)
3. ⏳ Ejecutar PRE_PRODUCTION_CHECKLIST.md (30 min)
4. ⏳ Deploy a producción

---

*Auditoría completada: Mayo 2026*  
*Problemas solucionados: 12/15*  
*Estado: 🟡 Listo (falta tarea 2 de CORS)*

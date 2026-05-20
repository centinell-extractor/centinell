# ✅ Pre-Producción Checklist - Centinell

Use esta lista para verificar que todo está configurado antes de desplegar.

---

## 🔐 SEGURIDAD

- [ ] **Variables de entorno**
  - [ ] DATABASE_URL configurada (PostgreSQL)
  - [ ] OPENAI_API_KEY configurada
  - [ ] .env está en .gitignore (no versionado)
  - [ ] .env.example NO contiene secretos reales

- [ ] **Secretos**
  - [ ] OPENAI_API_KEY no escrita en código
  - [ ] DATABASE_URL no escrita en código
  - [ ] Credenciales en vault o secrets manager

- [ ] **CORS**
  - [ ] Cambiar `allow_origins=["*"]` a dominios específicos
  - [ ] Revisar allow_methods y allow_headers

---

## 🚀 ESCALABILIDAD

- [ ] **Límites configurados**
  - [ ] MAX_DOCUMENT_SIZE_MB (actual: 5)
  - [ ] LLM_TIMEOUT_SECONDS (actual: 120)
  - [ ] LLM_RETRY_ATTEMPTS (actual: 3)
  - [ ] MAX_CONCURRENT_EXTRACTIONS (actual: 10)

- [ ] **Base de datos**
  - [ ] Índices creados (check en migration o DDL)
  - [ ] Connection pooling configurado
  - [ ] Backups automatizados

- [ ] **Rate Limiting**
  - [ ] ⚠️ PENDIENTE: Implementar SlowAPI
  - [ ] Threshold: 100 req/min por IP (recomendado)

---

## 📊 OBSERVABILIDAD

- [ ] **Logging**
  - [ ] Revisar logs en /var/log o stdout
  - [ ] ⚠️ PENDIENTE: Cambiar a JSON logging
  - [ ] Logs de retry attempts del LLM

- [ ] **Healthcheck**
  - [ ] GET /health devuelve 200
  - [ ] Configurado en load balancer

- [ ] **Métricas**
  - [ ] ⚠️ PENDIENTE: Prometheus exporter
  - [ ] Trackear: latencia LLM, error rate, extracciones/min

---

## 🧪 TESTING

- [ ] **Pruebas manuales**
  - [ ] POST /extract-test con documento pequeño
  - [ ] POST /extract con configuración real
  - [ ] GET /prompt-configs con paginación
  - [ ] Verificar retry logic (simular timeout)

- [ ] **Pruebas de carga**
  - [ ] ⚠️ PENDIENTE: Locust test con 10+ usuarios concurrentes
  - [ ] Verificar que no exceda MAX_CONCURRENT_EXTRACTIONS

- [ ] **Manejo de errores**
  - [ ] [ ] Documento > MAX_DOCUMENT_SIZE_MB → 413
  - [ ] [ ] API_KEY invalida → 500 (sin stack trace)
  - [ ] [ ] LLM timeout → retry 3 veces, luego 500

---

## 📦 DEPLOYMENT

- [ ] **Docker**
  - [ ] ⚠️ PENDIENTE: Dockerfile creado
  - [ ] ⚠️ PENDIENTE: .dockerignore con .env

- [ ] **Ambiente de producción**
  - [ ] DATABASE_URL apunta a prod PostgreSQL
  - [ ] OPENAI_API_KEY es cuenta de prod
  - [ ] LLM_TIMEOUT_SECONDS ajustado según latencia observada

- [ ] **Monitoreo**
  - [ ] Alertas: error rate > 5%
  - [ ] Alertas: latencia promedio > 30s
  - [ ] Alertas: DB connection pool exhausted

---

## 🔄 CONTINUIDAD

- [ ] **Backups**
  - [ ] Backups de BD cada 24h
  - [ ] Plan de recuperación probado

- [ ] **Versioning**
  - [ ] Tag git en deployment: `v1.0.0-prod`
  - [ ] Changelog actualizado

- [ ] **Rollback plan**
  - [ ] Proceso documentado para rollback
  - [ ] Blue-green deployment (si posible)

---

## ⚠️ PROBLEMAS CONOCIDOS (No Bloqueantes)

| Problema | Severidad | Workaround |
|----------|-----------|-----------|
| Sin rate limiting | Media | Monitorear manualmente o usar WAF |
| Logs no estructurados | Media | Implementar en sprintión 1.1 |
| Sin PDF timeout | Baja | Limitar tamaño de PDF a 5MB |
| CORS permisivo | Alta | ⚠️ CORREGIR ANTES DE PROD |

---

## 🎯 ESTADO ACTUAL

**Fecha de checklist**: Mayo 2026  
**Versión**: 1.0.0  
**Estado**: 🟡 CASI LISTO (falta CORS y rate limiting)

**Bloqueadores para producción**:
1. ⚠️ CORS: Cambiar `allow_origins=["*"]` a dominios específicos
2. ⚠️ Rate limiting: Implementar SlowAPI (2h trabajo)

**Después de corregir bloqueadores**: 🟢 LISTO PARA PRODUCCIÓN

---

## 📋 Sign-off

- [ ] QA: Verificó casos de prueba
- [ ] DevOps: Infraestructura lista
- [ ] Security: Revisó configuración
- [ ] Product: Aprobó para producción

**Responsable deployment**: _________________  
**Fecha**: _________________

---

## 📚 Referencia rápida

```bash
# Verificar logs
tail -f /var/log/centinell.log

# Health check
curl http://localhost:8000/health

# Test extracción
curl -X POST http://localhost:8000/extract-test \
  -H "Content-Type: application/json" \
  -d '{"document_text":"...", "variables":[...]}'

# Listar configs con paginación
curl http://localhost:8000/prompt-configs?skip=0&limit=10
```

---

**Mantener este checklist actualizado y revisar antes de cada deployment.**

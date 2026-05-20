# Checklist de Arquitectura para Produccion (Escalable y Segura)

## A. Seguridad
- [ ] Secrets en gestor seguro (no en .env de servidor productivo).
- [ ] Rotacion de secrets definida (API keys, JWT secret).
- [ ] TLS extremo a extremo.
- [ ] Cifrado en reposo para datos sensibles y storage documental.
- [ ] Password hashing robusto (Argon2 o bcrypt coste adecuado).
- [ ] Rate limiting en login y endpoints de alto coste.
- [ ] Politica RBAC por BU aplicada en backend.
- [ ] Logs sin secretos ni datos sensibles en claro.
- [ ] Headers de seguridad HTTP habilitados.
- [ ] Dependencias escaneadas por vulnerabilidades.

## B. Multi-tenancy (BU)
- [ ] Todas las tablas de negocio incluyen bu_id.
- [ ] Indices por bu_id en consultas frecuentes.
- [ ] Tests de no-fuga entre BU en endpoints criticos.
- [ ] Auditoria registra actor, bu_id, recurso y accion.
- [ ] Admin global separado de permisos BU locales.

## C. Escalabilidad
- [ ] API stateless y replicable horizontalmente.
- [ ] Trabajo pesado de extraccion desacoplado en worker.
- [ ] Cola de tareas con reintentos y backoff.
- [ ] DLQ para tareas fallidas recurrentes.
- [ ] Paginacion por cursor en listados grandes.
- [ ] Limites de concurrencia para llamadas LLM.
- [ ] Circuit breaker para proveedor LLM.
- [ ] Cache selectiva para configuraciones y metadatos frecuentes.

## D. Base de datos
- [ ] Migraciones versionadas y reversibles.
- [ ] Indices para documentos, runs e historial por bu_id y fecha.
- [ ] Politica de retencion de auditoria.
- [ ] Backups automaticos probados.
- [ ] Plan de restauracion validado.

## E. Storage documental
- [ ] Abstraccion de provider (local dev, objeto prod).
- [ ] Antivirus o escaneo de archivos (si aplica compliance).
- [ ] Control de tipo MIME y tamano maximo.
- [ ] URL de descarga firmada o proxy con auth.
- [ ] Politica de retencion y borrado seguro.

## F. Observabilidad
- [ ] Correlation-ID por request.
- [ ] Metricas: p50/p95/p99, throughput, error rate.
- [ ] Dashboard de estado API + worker + DB + cola.
- [ ] Alertas por SLO (latencia, error, backlog cola).
- [ ] Trazas distribuidas en llamadas criticas.

## G. Resiliencia y operacion
- [ ] Health checks (liveness/readiness).
- [ ] Timeouts y retries acotados en integraciones externas.
- [ ] Idempotencia para creacion de ejecuciones.
- [ ] Estrategia de despliegue sin downtime (rolling/canary).
- [ ] Runbook de incidentes y on-call definido.

## H. QA y cumplimiento
- [ ] Test unitarios en dominio critico.
- [ ] Test integracion para auth + BU isolation.
- [ ] Test de carga basico en endpoints de documentos/runs.
- [ ] Test de seguridad (OWASP baseline).
- [ ] Evidencia de auditoria exportable.

## Gate de salida a produccion
Se autoriza produccion solo si:
1. Todas las casillas A-B-F estan completas.
2. Al menos 90% de casillas C-D-E-G-H completadas.
3. No hay hallazgos criticos abiertos de seguridad.
4. Existe rollback probado del despliegue actual.

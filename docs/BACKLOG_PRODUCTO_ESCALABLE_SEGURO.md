# Backlog de Producto Escalable, Masivo y Seguro

## 1. Objetivo
Construir Centinell como plataforma multi-BU para extraccion documental con trazabilidad completa, control de acceso robusto y capacidad de operacion masiva.

## 2. Principios de arquitectura
- Aislamiento por BU en todas las entidades de negocio.
- Seguridad por defecto: deny by default, minimo privilegio, secretos fuera de repositorio.
- Escalabilidad horizontal de API y workers asincromos.
- Trazabilidad end-to-end por IDs y auditoria.
- Observabilidad obligatoria para operar en produccion.

## 3. Modelo de dominio minimo
- BU
- User
- UserBUAccess
- Document
- ExtractionRun
- VariableConfig
- ExtractionResult
- AuditEvent

Todos los recursos deben incluir:
- id (UUID v7 recomendado)
- bu_id (excepto entidades globales estrictamente necesarias)
- created_at
- updated_at
- created_by

## 4. Backlog por epicas

### EPICA A - Multi-BU y control de acceso
Objetivo: separar datos y permisos por BU.

Historias:
1. Como admin global quiero crear BU para separar operaciones por unidad.
Criterios de aceptacion:
- Se crea BU con ID unico.
- Nombre unico por tenant.
- Log de auditoria de alta.

2. Como admin global quiero asignar usuarios a BU con rol para controlar accesos.
Criterios de aceptacion:
- Roles minimos: admin_global, bu_admin, bu_user.
- Un usuario puede pertenecer a multiples BU.
- Revocacion de acceso efectiva de inmediato.

3. Como usuario autenticado quiero acceder solo a recursos de mis BU.
Criterios de aceptacion:
- Filtro por bu_id en todos los listados.
- Acceso cruzado entre BU bloqueado.
- Tests de autorizacion por endpoint.

### EPICA B - Identidad, autenticacion y sesion
Objetivo: login seguro con control de sesion.

Historias:
1. Como usuario quiero iniciar sesion para usar la plataforma.
Criterios de aceptacion:
- JWT access token y refresh token.
- Expiracion corta de access token.
- Revocacion de refresh token.

2. Como seguridad quiero hardening de autenticacion.
Criterios de aceptacion:
- Hash de password fuerte (Argon2 o bcrypt con coste alto).
- Rate limit en login.
- Bloqueo temporal tras intentos fallidos.

### EPICA C - Gestion de documentos
Objetivo: subir, listar y abrir documentos por BU.

Historias:
1. Como usuario quiero subir documentos para extraer datos.
Criterios de aceptacion:
- Validacion de tipo/tamano.
- Antimalware opcional por pipeline.
- Metadatos persistidos con document_id.

2. Como usuario quiero ver listado y detalle de documentos.
Criterios de aceptacion:
- Listado paginado y filtrable.
- Vista detalle con ejecuciones del documento.
- Desde historial, clic en documento abre misma vista detalle.

3. Como sistema quiero almacenar archivos de forma escalable.
Criterios de aceptacion:
- Abstraccion de storage (local para dev, objeto para prod).
- URL firmada o proxy seguro de descarga.
- Politica de retencion configurable.

### EPICA D - Ejecuciones y resultados de extraccion
Objetivo: operar ejecuciones confiables y trazables.

Historias:
1. Como usuario quiero lanzar una ejecucion sobre un documento.
Criterios de aceptacion:
- run_id unico y estado (queued, running, completed, failed).
- Reintentos controlados para fallos transitorios.
- Timeout configurable.

2. Como usuario quiero ver resultados por variable y evidencia.
Criterios de aceptacion:
- Panel izquierdo: variable + valor + confianza.
- Panel derecho: visor documento paginado/scroll.
- Lupa por variable navega a evidencia (pagina + snippet, y bbox cuando aplique).

3. Como usuario quiero ver razonamiento o descripcion de variable.
Criterios de aceptacion:
- Boton por variable para detalle.
- Modo seguro: no exponer prompts sensibles en bruto.

### EPICA E - Configuracion de variables con placeholders
Objetivo: permitir dependencias entre variables sin reprocesar todo el documento.

Historias:
1. Como configurador quiero usar placeholders tipo {{variable_anterior}}.
Criterios de aceptacion:
- Parser de placeholders.
- Resolucion en orden topologico.
- Error claro ante variable inexistente.

2. Como sistema quiero prevenir ciclos.
Criterios de aceptacion:
- Deteccion de ciclos (A->B->A).
- Bloqueo de guardado si hay ciclo.
- Mensaje de validacion accionable.

### EPICA F - Historial y navegacion unificada
Objetivo: trazabilidad y acceso rapido a informacion historica.

Historias:
1. Como usuario quiero consultar historial de ejecuciones por BU.
Criterios de aceptacion:
- Filtros por documento, fecha, estado, configuracion.
- Paginacion estable por cursor.
- Exportacion CSV/JSON asincrona para volumen alto.

2. Como usuario quiero navegar desde historial al documento y resultado.
Criterios de aceptacion:
- Clic en documento abre detalle de documento.
- Clic en ejecucion abre vista de resultados.

### EPICA G - Observabilidad, auditoria y cumplimiento
Objetivo: operar en produccion con control y evidencia.

Historias:
1. Como operador quiero metricas y alertas.
Criterios de aceptacion:
- p95/p99 latencia por endpoint.
- Tasa de error por tipo.
- Alertas por degradacion y fallo de dependencias.

2. Como auditor quiero registro de eventos criticos.
Criterios de aceptacion:
- AuditEvent para login, CRUD de configs, ejecuciones, cambios de rol.
- Correlation id por request.
- Retencion y busqueda por actor y recurso.

### EPICA H - Frontend producto
Objetivo: UX clara para operar a escala.

Historias:
1. Menu lateral con secciones: Documentos, Extracciones, Configuracion, Historial, Admin BU.
Criterios de aceptacion:
- Documentos es primera seccion.
- Navegacion consistente entre detalle de documento e historial.

2. Vista de resultados en dos paneles con lupa y razonamiento.
Criterios de aceptacion:
- Layout responsive desktop/mobile.
- Sin bloqueo de UI en documentos largos.

### EPICA I - Performance y escalabilidad masiva
Objetivo: soportar volumen alto con calidad de servicio.

Historias:
1. Como plataforma quiero procesamiento asincrono por cola.
Criterios de aceptacion:
- API encola ejecucion y devuelve run_id.
- Worker independiente procesa tareas.
- Reintentos con backoff y DLQ.

2. Como plataforma quiero optimizacion de datos.
Criterios de aceptacion:
- Indices en consultas de historial y documentos.
- Paginacion por cursor en listados grandes.
- N+1 evitado en endpoints criticos.

## 5. Requisitos no funcionales obligatorios

### Seguridad
- OWASP ASVS como baseline.
- Secrets en gestor de secretos, nunca en repo.
- Cifrado en transito (TLS) y en reposo para storage sensible.
- Politica de permisos por rol y BU en backend, nunca solo en frontend.
- Sanitizacion de logs para evitar fuga de datos sensibles.

### Escalabilidad
- API stateless para escalar horizontalmente.
- Cola de trabajos para extracciones pesadas.
- LLM calls con circuit breaker, timeout y retry acotado.
- Caching selectivo de metadatos y configs.

### Disponibilidad y resiliencia
- Health checks y readiness/liveness.
- Degradacion controlada ante caida de proveedor LLM.
- Idempotencia en operaciones de creacion de ejecuciones.

## 6. Priorizacion por releases

### Release 1 (Base segura)
- EPICA A, B (MVP), C (subida/listado), D (run basico), G (audit minimo).
- Meta: producto usable por BU con login y trazabilidad.

### Release 2 (UX operativa)
- EPICA D completa (lupa/razonamiento), E completa, F completa, H completa.
- Meta: flujo completo de trabajo de analista.

### Release 3 (Escala masiva)
- EPICA I completa + endurecimiento G (alertas avanzadas).
- Meta: operacion estable a gran volumen.

## 7. Definicion de Done (DoD)
- Tests unitarios y de integracion verdes.
- Pruebas de autorizacion multi-BU.
- Registro de auditoria para eventos relevantes.
- Documentacion API y runbook operacion actualizados.
- Sin secretos en codigo, repositorio ni logs.

## 8. Siguiente sprint recomendado (2 semanas)
1. Crear entidades y migraciones base multi-BU + IDs.
2. Implementar login JWT + roles + middleware de autorizacion.
3. Entregar API de documentos por BU (upload/list/detail).
4. Entregar API de ejecuciones por documento con run_id y estados.
5. Implementar pantalla Documentos (listado + detalle + navegacion desde historial).

# Sprint R1 - Plan Operativo (2 semanas)

## Objetivo
Entregar la base segura y multi-BU del producto para operar documentos y ejecuciones con login, autorizacion y trazabilidad.

## Alcance del sprint
- Multi-BU base (modelo y permisos).
- Login JWT + refresh + roles.
- Documentos por BU (upload/list/detail).
- Ejecuciones basicas por documento (run_id + estados).
- Auditoria minima y observabilidad basica.

## Fuera de alcance (este sprint)
- Lupa de evidencia en visor.
- Placeholders entre variables.
- Historial avanzado con exportaciones.
- Cola distribuida completa con DLQ (queda para R3).

## Backlog ejecutable por historias

### R1-01 - Modelo de datos multi-BU
Descripcion: crear tablas y relaciones base para aislamiento por BU.
Entregables:
- Migraciones para: business_units, users, user_bu_access, documents, extraction_runs, audit_events.
- IDs UUIDv7 en todas las entidades nuevas.
- Indices base: (bu_id, created_at), (document_id, created_at), (user_id, bu_id).
Criterios de aceptacion:
- Todas las consultas de negocio incluyen bu_id.
- No hay acceso cruzado entre BU por diseno de queries.
Estimacion: 2 dias.
Dependencias: ninguna.

### R1-02 - Autenticacion y autorizacion
Descripcion: implementar login y control de acceso por rol y BU.
Entregables:
- Endpoint login con JWT access/refresh.
- Endpoint refresh token.
- Dependencia/guard de autorizacion por rol y bu_id.
- Hash de password seguro (bcrypt o Argon2).
Criterios de aceptacion:
- Usuario sin acceso a BU recibe 403.
- Token expirado devuelve 401.
- Tests de auth en endpoints protegidos.
Estimacion: 2 dias.
Dependencias: R1-01.

### R1-03 - API de documentos por BU
Descripcion: permitir subir y consultar documentos de forma aislada por BU.
Entregables:
- POST /documents (upload).
- GET /documents (listado paginado por BU).
- GET /documents/{document_id} (detalle).
- Almacenamiento local abstracto (interfaz preparada para objeto storage).
Criterios de aceptacion:
- Validacion de tamano y tipo de archivo.
- Documento queda asociado a bu_id y created_by.
- Listado no muestra documentos de otras BU.
Estimacion: 2 dias.
Dependencias: R1-01, R1-02.

### R1-04 - API de ejecuciones basicas
Descripcion: registrar y ejecutar extracciones basicas por documento.
Entregables:
- POST /extract (crea run_id y estado inicial).
- GET /extractions/{run_id} (estado y resultado basico).
- GET /documents/{document_id}/runs (listado de ejecuciones).
Criterios de aceptacion:
- Estados validos: queued, running, completed, failed.
- run_id unico y trazable a document_id.
- Timeout y retries basicos respetados.
Estimacion: 2 dias.
Dependencias: R1-03.

### R1-05 - Auditoria minima y observabilidad
Descripcion: registrar eventos y metricas esenciales.
Entregables:
- Audit event para login, upload, run creation, cambios de rol.
- Correlation id por request.
- Metricas minimas por endpoint: latency, error rate.
Criterios de aceptacion:
- Eventos auditables consultables por actor y recurso.
- Logs sin secretos.
Estimacion: 1.5 dias.
Dependencias: R1-02, R1-03, R1-04.

### R1-06 - Front inicial de Documentos
Descripcion: construir navegacion base y vista de documentos.
Entregables:
- Menu lateral con Documentos como primer item.
- Listado de documentos.
- Vista detalle de documento con lista de ejecuciones.
- Enlace desde historial al detalle de documento.
Criterios de aceptacion:
- Navegacion consistente entre pantallas.
- Carga correcta en desktop y mobile.
Estimacion: 1.5 dias.
Dependencias: R1-03, R1-04.

## Plan diario sugerido
- Dia 1-2: R1-01
- Dia 3-4: R1-02
- Dia 5-6: R1-03
- Dia 7-8: R1-04
- Dia 9: R1-05
- Dia 10: R1-06 + hardening + demo

## Riesgos y mitigaciones
- Riesgo: acoplar auth y BU tarde.
Mitigacion: R1-02 antes de cerrar APIs de negocio.
- Riesgo: N+1 y latencia en listados.
Mitigacion: indices y paginacion desde R1-01/R1-03.
- Riesgo: fuga de datos en logs.
Mitigacion: mascarado de secretos y pruebas de logging.

## Criterio de cierre del sprint
- Demo funcional: login, documentos por BU, ejecucion basica, historial de runs.
- Tests de auth y aislamiento multi-BU en verde.
- Checklist de seguridad basica completado.

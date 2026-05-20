# API Contratos R1 (Base segura y multi-BU)

## Convenciones
- Auth: Bearer JWT en header Authorization.
- Contexto BU: header X-BU-ID obligatorio en endpoints de negocio.
- IDs: UUID (preferible UUIDv7).
- Errores comunes:
  - 400 bad_request
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
  - 409 conflict
  - 422 validation_error
  - 500 internal_error

## 1) Autenticacion

### POST /auth/login
Request:
```json
{
  "email": "admin@empresa.com",
  "password": "string"
}
```
Response 200:
```json
{
  "access_token": "jwt",
  "refresh_token": "jwt",
  "token_type": "bearer",
  "expires_in": 900,
  "user": {
    "id": "uuid",
    "email": "admin@empresa.com",
    "role": "admin_global"
  }
}
```

### POST /auth/refresh
Request:
```json
{
  "refresh_token": "jwt"
}
```
Response 200:
```json
{
  "access_token": "jwt",
  "token_type": "bearer",
  "expires_in": 900
}
```

## 2) Business Units

### POST /bus
Role requerido: admin_global
Request:
```json
{
  "name": "Finance",
  "code": "FIN"
}
```
Response 201:
```json
{
  "id": "uuid",
  "name": "Finance",
  "code": "FIN",
  "created_at": "2026-05-20T12:00:00Z"
}
```

### GET /bus
Role requerido: admin_global
Response 200:
```json
{
  "items": [
    {
      "id": "uuid",
      "name": "Finance",
      "code": "FIN"
    }
  ],
  "total": 1
}
```

## 3) Asignacion de usuarios a BU

### POST /bus/{bu_id}/users
Role requerido: admin_global o bu_admin
Request:
```json
{
  "user_id": "uuid",
  "role": "bu_user"
}
```
Response 201:
```json
{
  "id": "uuid",
  "bu_id": "uuid",
  "user_id": "uuid",
  "role": "bu_user"
}
```

## 4) Documentos

### POST /documents
Headers:
- Authorization: Bearer <token>
- X-BU-ID: <uuid>
Content-Type: multipart/form-data
Fields:
- file: binary
- title: string (opcional)

Response 201:
```json
{
  "id": "uuid",
  "bu_id": "uuid",
  "title": "factura_abril.pdf",
  "filename": "factura_abril.pdf",
  "mime_type": "application/pdf",
  "size_bytes": 124553,
  "created_by": "uuid",
  "created_at": "2026-05-20T12:00:00Z"
}
```

### GET /documents?cursor=<string>&limit=20
Headers:
- Authorization
- X-BU-ID

Response 200:
```json
{
  "items": [
    {
      "id": "uuid",
      "title": "factura_abril.pdf",
      "created_at": "2026-05-20T12:00:00Z"
    }
  ],
  "next_cursor": "opaque-cursor-or-null"
}
```

### GET /documents/{document_id}
Headers:
- Authorization
- X-BU-ID

Response 200:
```json
{
  "id": "uuid",
  "bu_id": "uuid",
  "title": "factura_abril.pdf",
  "storage_key": "docs/uuid.pdf",
  "created_by": "uuid",
  "created_at": "2026-05-20T12:00:00Z"
}
```

## 5) Ejecuciones

### POST /extract
Headers:
- Authorization
- X-BU-ID
Request:
```json
{
  "document_id": "uuid",
  "prompt_config_id": "uuid"
}
```
Response 202:
```json
{
  "run_id": "uuid",
  "document_id": "uuid",
  "status": "queued",
  "created_at": "2026-05-20T12:00:00Z"
}
```

### GET /extractions/{run_id}
Headers:
- Authorization
- X-BU-ID

Response 200:
```json
{
  "run_id": "uuid",
  "document_id": "uuid",
  "status": "completed",
  "started_at": "2026-05-20T12:00:05Z",
  "finished_at": "2026-05-20T12:00:12Z",
  "results": [
    {
      "variable": "importe_total",
      "value": "1234.56",
      "confidence": 0.93
    }
  ]
}
```

### GET /documents/{document_id}/runs?cursor=<string>&limit=20
Headers:
- Authorization
- X-BU-ID

Response 200:
```json
{
  "items": [
    {
      "run_id": "uuid",
      "status": "failed",
      "created_at": "2026-05-20T12:00:00Z"
    }
  ],
  "next_cursor": null
}
```

## 6) Auditoria minima

### GET /audit-events?actor_id=<uuid>&resource_type=document&limit=50
Headers:
- Authorization
- X-BU-ID (excepto admin_global con vista global)

Response 200:
```json
{
  "items": [
    {
      "id": "uuid",
      "event_type": "document.uploaded",
      "actor_id": "uuid",
      "resource_type": "document",
      "resource_id": "uuid",
      "created_at": "2026-05-20T12:00:00Z",
      "correlation_id": "uuid"
    }
  ],
  "total": 1
}
```

## Matriz de autorizacion resumida
- admin_global: acceso total multi-BU.
- bu_admin: admin dentro de su BU.
- bu_user: operacion de negocio dentro de su BU, sin admin de usuarios.

## Reglas de seguridad de contrato
- Nunca aceptar bu_id en body cuando existe X-BU-ID (evitar spoofing).
- Validar pertenencia de recurso a X-BU-ID antes de responder.
- En errores 401/403 no exponer detalles sensibles.
- Aplicar rate limit en /auth/login y /extract.

# Guía rápida de Centinell

## Qué hace la app
Centinell expone una API FastAPI para definir configuraciones de extracción, construir prompts para un LLM y devolver resultados estructurados desde texto de documentos.

## Rutas más importantes
- [app/main.py](../app/main.py) registra todos los routers de la aplicación.
- `POST /prompt-configs/` crea una configuración de prompt con variables y validaciones.
- `GET /prompt-configs/` lista configuraciones guardadas.
- `POST /extract/` ejecuta una extracción real usando una configuración guardada en base de datos.
- `POST /extract-test/` prueba una extracción con variables enviadas en el request, sin depender de la BD.
- `GET /test-template/` devuelve un prompt de ejemplo ya ensamblado para revisar el formato final.

## Funciones y módulos clave
- [app/config.py](../app/config.py) carga las variables de entorno con `load_dotenv` y valida que exista `DATABASE_URL`.
- [app/db/connection.py](../app/db/connection.py) crea la conexión async a la base de datos y la dependencia `get_db`.
- [app/db/models.py](../app/db/models.py) define las tablas `prompt_configs` y `extractions`.
- [app/schemas/prompt_config.py](../app/schemas/prompt_config.py) define los esquemas Pydantic para crear y leer configuraciones.
- [app/services/template_engine.py](../app/services/template_engine.py) construye el prompt final a partir de las variables.
- [app/services/llm_client.py](../app/services/llm_client.py) llama a OpenAI y valida la respuesta.
- [app/services/response_validator.py](../app/services/response_validator.py) normaliza y valida el JSON devuelto por el modelo.
- [app/routers/prompt_configs.py](../app/routers/prompt_configs.py) valida `{{VARIABLE_BLOCK}}` y evita nombres de variables duplicados.
- [app/routers/extract.py](../app/routers/extract.py) carga la configuración activa, llama al LLM y guarda el resultado en `extractions`.

## Variables que debes guardar en un archivo
Las variables sensibles y de entorno deben ir en un archivo local no versionado, normalmente `.env`.

### Mínimas para que funcione
- `DATABASE_URL`: URL completa de conexión a la base de datos.
- `OPENAI_API_KEY`: clave de OpenAI usada por `app/services/llm_client.py`.

### Opcionales o de desarrollo
- `USE_SQLITE`: útil si quieres forzar un entorno local con SQLite, como sugiere `.env.dev`.

## Dónde guardarlas
- Usa [./.env](../.env) para tus valores reales locales. No debe subirse al repositorio.
- Usa [./.env.dev](../.env.dev) solo como referencia para desarrollo local con SQLite.
- Si quieres compartir la estructura sin secretos, usa el nuevo [./.env.example](../.env.example).

## Flujo recomendado
1. Define `DATABASE_URL` y `OPENAI_API_KEY` en `.env`.
2. Arranca la app desde [app/main.py](../app/main.py).
3. Crea una configuración con `POST /prompt-configs/`.
4. Prueba el prompt con `GET /test-template/` o `POST /extract-test/`.
5. Ejecuta la extracción real con `POST /extract/`.

## Nota importante
No guardes claves reales dentro del código fuente ni dentro de archivos que quieras compartir. Si necesitas documentarlas, usa nombres de variables y ejemplos, no valores reales.

## Plan de implementación (10 dias)

Objetivo del plan: pasar de API funcional a producto usable de punta a punta con flujo guiado:
subir documento, crear o elegir prompt, ejecutar extracción, revisar y validar resultados.

### Entregables al final de 10 dias
- Frontend operativo con wizard de nueva extracción.
- Pantalla de configuraciones de prompt con editor de variables.
- Pantalla de historial y detalle de extracción.
- Captura de correcciones humanas para mejorar calidad.
- Métricas básicas de uso y calidad visibles.

### Día 1 - Contratos y alcance
- Definir contrato UI para 3 vistas MVP: Nueva extracción, Configuraciones, Historial.
- Definir estados de ejecución: draft, running, success, failed, validated.
- Criterio de aceptación: documento de contratos aprobado y sin ambigüedades.

### Día 2 - Base frontend
- Crear estructura del frontend (rutas, layout, navegación principal).
- Crear cliente API tipado para endpoints existentes.
- Criterio de aceptación: navegación funcional entre vistas vacías y llamadas GET funcionando.

### Día 3 - Nueva extracción (pasos 1 y 2)
- Paso 1: carga de documento (texto o archivo con preview de contenido).
- Paso 2: selector de configuración con búsqueda por nombre.
- Criterio de aceptación: el usuario puede preparar una ejecución completa sin lanzar todavía.

### Día 4 - Nueva extracción (pasos 3 y 4)
- Paso 3: ejecución contra POST /extract/ con estados de carga y error.
- Paso 4: tabla de resultados por variable con edición manual.
- Criterio de aceptación: flujo completo ejecutado al menos 3 veces sin bloqueo.

### Día 5 - Validación humana
- Añadir acciones por campo: aceptar, corregir, dejar nulo.
- Mostrar resumen de cambios manuales aplicados.
- Criterio de aceptación: quedan trazadas las correcciones y su conteo por ejecución.

### Día 6 - Configuraciones
- Lista de configuraciones con filtros básicos.
- Formulario de creación/edición de variables (name, type, required, regex, max_length).
- Criterio de aceptación: crear nueva configuración y usarla en una extracción real.

### Día 7 - Historial y detalle
- Tabla de historial consumiendo GET /extractions/ con filtros por estado y config.
- Vista detalle consumiendo GET /extractions/{id} mostrando prompt y respuesta cruda.
- Criterio de aceptación: se puede auditar de punta a punta una extracción pasada.

### Día 8 - Calidad y telemetría
- Instrumentar eventos mínimos: run_started, run_completed, run_failed, field_corrected.
- Mostrar 4 KPI en dashboard: latencia media, tasa de fallo, correcciones por ejecución, volumen diario.
- Criterio de aceptación: los KPI cambian al generar nuevas ejecuciones.

### Día 9 - Robustez UX
- Estados de vacio, errores recuperables y reintentos en frontend.
- Pulido de validaciones de formulario y mensajes para usuario no técnico.
- Criterio de aceptación: no hay pantallas bloqueantes ante fallos típicos de red o validación.

### Día 10 - Cierre MVP
- Prueba integral con casos reales (al menos 20 documentos).
- Lista de incidencias priorizadas para sprint siguiente.
- Criterio de aceptación: demo completa del flujo end-to-end sin intervención técnica.

### KPIs de producto que hay que seguir cada semana
- Tiempo medio desde carga hasta validación final.
- Porcentaje de campos corregidos manualmente.
- Tasa de éxito/fallo por configuración.
- Latencia media por extracción.
- Reutilización de configuraciones (ejecuciones por config).

### Riesgos y mitigación
- Riesgo: prompts muy largos por exceso de variables.
	Mitigación: dividir en configuraciones por dominio (identificación, importes, fechas).
- Riesgo: caída de calidad al cambiar prompt o modelo.
	Mitigación: mantener set de pruebas de regresión con documentos reales anonimizados.
- Riesgo: UX demasiado técnica.
	Mitigación: lenguaje de negocio y wizard guiado con una acción principal por paso.
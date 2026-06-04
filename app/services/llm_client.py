# app/services/llm_client.py
import json
import asyncio
from typing import List, Dict, Any, TypedDict, Optional
import httpx
from app.config import (
    OPENAI_API_KEY, 
    LLM_TIMEOUT_SECONDS, 
    LLM_MAX_TIMEOUT_SECONDS,
    LLM_RETRY_ATTEMPTS,
    LLM_RETRY_DELAY_SECONDS
)
from app.services.template_engine import build_final_prompt, parse_var_refs
from app.services.response_validator import validate_and_clean_response, ResponseValidationError
import logging

logger = logging.getLogger(__name__)

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-4o"


class LLMExtractionError(Exception):
    pass


class LLMExtractionResult(TypedDict):
    prompt_sent: str
    raw_llm_response: str
    cleaned: List[Dict[str, Any]]
    # Conteo de tokens OpenAI (para tracking de uso y costes)
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model_used: str


def _extract_api_error_message(resp: httpx.Response) -> str:
    """Extrae un mensaje de error corto y seguro desde la respuesta del proveedor."""
    try:
        data = resp.json()
    except ValueError:
        return "No se pudo parsear el detalle del error del proveedor."

    if isinstance(data, dict):
        error_obj = data.get("error", {})
        if isinstance(error_obj, dict):
            message = error_obj.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()[:300]

    return "No se pudo obtener detalle del error del proveedor."


async def call_llm_for_extraction(
    document_text: str,
    variables: List[Dict[str, Any]],
    model: str = DEFAULT_MODEL,
    base_prompt: Optional[str] = None,
    timeout_seconds: Optional[int] = None,
    temperature: float = 0.0,
) -> LLMExtractionResult:
    """
    Construye el prompt con el template engine, llama al modelo de IA con retry logic
    y devuelve prompt enviado, respuesta cruda y lista validada [{title, answer}, ...].
    
    Args:
        document_text: Contenido del documento a procesar
        variables: Lista de variables a extraer
        model: Modelo LLM a usar (default: gpt-4o)
        base_prompt: Prompt personalizado (usa default si no se proporciona)
        timeout_seconds: Timeout en segundos (default: LLM_TIMEOUT_SECONDS, max: LLM_MAX_TIMEOUT_SECONDS)
    """
    if not OPENAI_API_KEY:
        raise LLMExtractionError("OPENAI_API_KEY no está definida.")

    # Validar y configurar timeout
    if timeout_seconds is None:
        timeout_seconds = LLM_TIMEOUT_SECONDS
    timeout_seconds = min(timeout_seconds, LLM_MAX_TIMEOUT_SECONDS)
    if timeout_seconds < 10:
        timeout_seconds = 10

    final_prompt = build_final_prompt(variables, base_prompt=base_prompt)
    final_prompt = (
        f"{final_prompt}\n\n"
        "REQUISITO DE TRAZABILIDAD: En cada item del JSON incluye tambien:\n"
        "- 'reasoning': razonamiento detallado (3-5 frases) que explique: (1) que evidencia concreta"
        " del documento soporta la respuesta, (2) en que seccion o contexto aparece esa informacion,"
        " (3) como se interpreto si habia ambiguedad o multiples candidatos, y (4) por que se"
        " descartaron otras posibles respuestas si las hubiera; null si el campo no aplica al documento.\n"
        "- 'source_quote': cita LITERAL e IDENTICA al texto del documento (maximo 300 caracteres)"
        " que contiene la informacion extraida; debe ser copiada exactamente como aparece en el"
        " documento, sin parafrasis ni resumen; null si no aplica"
    )

    system_message = {
        "role": "system",
        "content": final_prompt,
    }
    user_message = {
        "role": "user",
        "content": f"Contenido del documento:\n\n{document_text}",
    }

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "temperature": max(0.0, min(2.0, float(temperature))),
        "messages": [system_message, user_message],
    }

    # Retry logic con exponential backoff
    last_error = None
    for attempt in range(LLM_RETRY_ATTEMPTS):
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                resp = await client.post(OPENAI_API_URL, headers=headers, json=payload)

            if resp.status_code == 401:
                raise LLMExtractionError(
                    "Autenticacion OpenAI fallida (401): API key invalida o deshabilitada. "
                    "Genera una clave nueva, actualiza OPENAI_API_KEY en .env y reinicia el servicio."
                )

            if resp.status_code == 429:  # Rate limited
                wait_time = LLM_RETRY_DELAY_SECONDS * (2 ** attempt)
                logger.warning(f"Rate limited. Reintentando en {wait_time}s (intento {attempt + 1}/{LLM_RETRY_ATTEMPTS})")
                await asyncio.sleep(wait_time)
                continue

            if resp.status_code == 403:
                error_message = _extract_api_error_message(resp)
                raise LLMExtractionError(
                    f"OpenAI rechazo la solicitud (403). Verifica permisos/proyecto de la API key. Detalle: {error_message}"
                )

            if 400 <= resp.status_code < 500:
                error_message = _extract_api_error_message(resp)
                raise LLMExtractionError(
                    f"Error de solicitud a OpenAI (HTTP {resp.status_code}). Detalle: {error_message}"
                )

            if resp.status_code != 200:
                error_detail = f"HTTP {resp.status_code}"
                if attempt < LLM_RETRY_ATTEMPTS - 1:
                    logger.warning(f"Error en LLM: {error_detail}. Reintentando... (intento {attempt + 1}/{LLM_RETRY_ATTEMPTS})")
                    await asyncio.sleep(LLM_RETRY_DELAY_SECONDS * (2 ** attempt))
                    continue
                raise LLMExtractionError(f"Error en llamada a LLM: {error_detail}")

            # Parsear respuesta
            try:
                data = resp.json()
            except json.JSONDecodeError as e:
                raise LLMExtractionError(f"Respuesta inválida de LLM: no es JSON válido") from e

            # Validar estructura de respuesta
            if not isinstance(data, dict):
                raise LLMExtractionError("Respuesta del LLM: estructura esperada es objeto")
            
            if "choices" not in data or not isinstance(data["choices"], list) or len(data["choices"]) == 0:
                raise LLMExtractionError("Respuesta del LLM: choices vacío o ausente")
            
            choice = data["choices"][0]
            if "message" not in choice or "content" not in choice["message"]:
                raise LLMExtractionError("Respuesta del LLM: message.content ausente")

            content = choice["message"]["content"]
            if not isinstance(content, str):
                raise LLMExtractionError("Respuesta del LLM: content no es string")

            # Limpiar markdown code blocks si los LLM los devuelven
            # Algunos LLMs devuelven: ```json [...] ``` en lugar de solo [...]
            cleaned_content = content.strip()
            if cleaned_content.startswith("```"):
                # Remover ```json o ``` al inicio
                cleaned_content = cleaned_content.lstrip("`").lstrip("json").lstrip("JSON").strip()
            if cleaned_content.endswith("```"):
                # Remover ``` al final
                cleaned_content = cleaned_content.rstrip("`").strip()

            logger.debug(f"Contenido del LLM antes de limpiar: {content[:100]}...")
            logger.debug(f"Contenido del LLM después de limpiar: {cleaned_content[:100]}...")

            # Parsear JSON de la respuesta
            try:
                raw_result = json.loads(cleaned_content)
            except json.JSONDecodeError as e:
                logger.error(f"JSON inválido recibido del LLM: {cleaned_content[:500]}")
                raise LLMExtractionError(
                    f"No se pudo parsear respuesta como JSON (después de limpiar markdown): {cleaned_content[:150]}..."
                ) from e

            # Validar y limpiar respuesta
            try:
                cleaned = validate_and_clean_response(raw_result, variables)
            except ResponseValidationError as e:
                raise LLMExtractionError(f"Respuesta del LLM inválida: {e}") from e

            # Capturar uso de tokens (disponible en todas las respuestas de la API)
            usage = data.get("usage") or {}

            # Éxito - retornar resultado
            return LLMExtractionResult(
                prompt_sent=final_prompt,
                raw_llm_response=content,
                cleaned=cleaned,
                prompt_tokens=int(usage.get("prompt_tokens", 0)),
                completion_tokens=int(usage.get("completion_tokens", 0)),
                total_tokens=int(usage.get("total_tokens", 0)),
                model_used=model,
            )

        except (httpx.TimeoutException, asyncio.TimeoutError) as e:
            last_error = e
            if attempt < LLM_RETRY_ATTEMPTS - 1:
                wait_time = LLM_RETRY_DELAY_SECONDS * (2 ** attempt)
                logger.warning(f"Timeout en LLM. Reintentando en {wait_time}s (intento {attempt + 1}/{LLM_RETRY_ATTEMPTS})")
                await asyncio.sleep(wait_time)
            else:
                raise LLMExtractionError(f"Timeout en LLM después de {LLM_RETRY_ATTEMPTS} intentos") from e

        except LLMExtractionError:
            raise  # Re-raise LLMExtractionError sin reintento

        except Exception as e:
            last_error = e
            if attempt < LLM_RETRY_ATTEMPTS - 1:
                logger.warning(f"Error inesperado en LLM: {str(e)}. Reintentando... (intento {attempt + 1}/{LLM_RETRY_ATTEMPTS})")
                await asyncio.sleep(LLM_RETRY_DELAY_SECONDS * (2 ** attempt))
            else:
                raise LLMExtractionError(f"Error en LLM después de {LLM_RETRY_ATTEMPTS} intentos: {str(e)}") from e

    # Si llegamos aquí, todos los reintentos fallaron
    raise LLMExtractionError(f"Falló extracción LLM después de {LLM_RETRY_ATTEMPTS} intentos: {str(last_error)}")


def _toposort_rounds(variables: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """
    Ordena las variables en rondas de ejecución según sus dependencias {{VarName}}.
    Las variables sin dependencias van en la primera ronda; las dependientes, después.
    Lanza ValueError si hay dependencias circulares.
    """
    known = {v["name"] for v in variables}
    by_name = {v["name"]: v for v in variables}

    deps = {
        v["name"]: parse_var_refs(v.get("description", ""), known) - {v["name"]}
        for v in variables
    }
    in_degree = {name: len(d) for name, d in deps.items()}

    rounds: List[List[Dict[str, Any]]] = []
    resolved: set = set()

    while len(resolved) < len(variables):
        current_names = [
            name for name in by_name
            if name not in resolved and in_degree[name] == 0
        ]
        if not current_names:
            raise ValueError("Dependencias circulares detectadas entre variables")

        rounds.append([by_name[name] for name in current_names])
        for name in current_names:
            resolved.add(name)
            for other_name, other_deps in deps.items():
                if name in other_deps and other_name not in resolved:
                    in_degree[other_name] -= 1

    return rounds


async def call_llm_for_extraction_chained(
    document_text: str,
    variables: List[Dict[str, Any]],
    model: str = DEFAULT_MODEL,
    base_prompt: Optional[str] = None,
    timeout_seconds: Optional[int] = None,
    temperature: float = 0.0,
) -> LLMExtractionResult:
    """
    Versión encadenada de call_llm_for_extraction.
    Si alguna variable referencia a otra via {{NombreVar}} en su descripción,
    las ejecuta en rondas secuenciales interpolando las respuestas previas.
    Si no hay dependencias, delega directamente a call_llm_for_extraction (sin overhead).
    """
    known_names = {v["name"] for v in variables}
    has_deps = any(
        parse_var_refs(v.get("description", ""), known_names)
        for v in variables
    )

    if not has_deps:
        return await call_llm_for_extraction(
            document_text, variables, model, base_prompt, timeout_seconds, temperature
        )

    rounds = _toposort_rounds(variables)
    logger.info(
        "Extracción encadenada: %d variables en %d rondas.",
        len(variables),
        len(rounds),
    )

    all_results: List[Dict[str, Any]] = []
    resolved_answers: Dict[str, Any] = {}
    all_prompts: List[str] = []
    all_raw: List[str] = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_tokens = 0

    for round_idx, round_vars in enumerate(rounds):
        # Interpolar respuestas anteriores en las descripciones de esta ronda
        interpolated = []
        for v in round_vars:
            desc = v.get("description", "")
            for ref_name, ref_answer in resolved_answers.items():
                desc = desc.replace(f"{{{{{ref_name}}}}}", str(ref_answer) if ref_answer is not None else "null")
            interpolated.append({**v, "description": desc})

        logger.info(
            "Ronda %d/%d: extrayendo %s",
            round_idx + 1,
            len(rounds),
            [v["name"] for v in interpolated],
        )

        round_result = await call_llm_for_extraction(
            document_text, interpolated, model, base_prompt, timeout_seconds, temperature
        )

        all_prompts.append(round_result["prompt_sent"])
        all_raw.append(round_result["raw_llm_response"])
        total_prompt_tokens     += round_result.get("prompt_tokens", 0)
        total_completion_tokens += round_result.get("completion_tokens", 0)
        total_tokens            += round_result.get("total_tokens", 0)

        for item in round_result["cleaned"]:
            all_results.append(item)
            resolved_answers[item["title"]] = item.get("answer")

    # Preservar el orden original de las variables
    original_order = {v["name"]: i for i, v in enumerate(variables)}
    all_results.sort(key=lambda x: original_order.get(x["title"], 999))

    return LLMExtractionResult(
        prompt_sent="\n\n--- RONDA SIGUIENTE ---\n\n".join(all_prompts),
        raw_llm_response="\n\n--- RONDA SIGUIENTE ---\n\n".join(all_raw),
        cleaned=all_results,
        prompt_tokens=total_prompt_tokens,
        completion_tokens=total_completion_tokens,
        total_tokens=total_tokens,
        model_used=model,
    )
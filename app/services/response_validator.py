# app/services/response_validator.py
from typing import List, Dict, Any, Optional


class ResponseValidationError(Exception):
    pass


def validate_and_clean_response(
    raw_result: List[Dict[str, Any]],
    variables: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Valida que la respuesta del modelo:
    - Sea una lista de objetos {title, answer, reasoning?}
    - Solo contenga titles esperados
    - Limpia y normaliza answer según el tipo de variable
    """

    # Mapa de variables por nombre (exact + case-insensitive fallback)
    var_by_name = {v["name"]: v for v in variables}
    var_by_name_lower = {v["name"].lower().strip(): v for v in variables}

    cleaned: List[Dict[str, Any]] = []

    if not isinstance(raw_result, list):
        raise ResponseValidationError("La respuesta no es una lista.")

    for item in raw_result:
        if not isinstance(item, dict):
            raise ResponseValidationError("Cada elemento de la respuesta debe ser un objeto JSON.")

        title = item.get("title")
        answer = item.get("answer")
        reasoning = item.get("reasoning")
        source_quote = item.get("source_quote")

        if title is None:
            raise ResponseValidationError("Falta el campo 'title' en algún elemento.")

        # Coincidencia exacta → case-insensitive → aceptar como string desconocido
        if title in var_by_name:
            var_def = var_by_name[title]
        elif isinstance(title, str) and title.lower().strip() in var_by_name_lower:
            var_def = var_by_name_lower[title.lower().strip()]
            title = var_def["name"]  # normalizar al nombre canónico
        else:
            # Título no pedido: el LLM extrajo algo extra. Lo incluimos tal cual
            # en lugar de rechazar toda la extracción.
            var_def = {"type": "string"}

        var_type = var_def.get("type", "string")

        # Normalizar answer
        if isinstance(answer, str):
            answer = answer.strip()
            if answer == "":
                answer = None

        # Aplicar reglas según tipo
        if answer is not None:
            if var_type == "number":
                # Intentar convertir a número
                answer = _normalize_number(answer)
            elif var_type == "string":
                # Opcional: recortar a max_length
                max_length = var_def.get("max_length")
                if max_length is not None and isinstance(answer, str):
                    answer = answer[:max_length]

        if isinstance(reasoning, str):
            reasoning = reasoning.strip() or None
        elif reasoning is not None:
            reasoning = str(reasoning)

        if isinstance(source_quote, str):
            source_quote = source_quote.strip()[:300] or None
        elif source_quote is not None:
            source_quote = str(source_quote)[:300]

        cleaned_item: Dict[str, Any] = {"title": title, "answer": answer}
        if reasoning is not None:
            cleaned_item["reasoning"] = reasoning
        if source_quote is not None:
            cleaned_item["source_quote"] = source_quote
        cleaned.append(cleaned_item)

    # Comprobar que todos los required tienen entrada (aunque sea null)
    for name, var_def in var_by_name.items():
        if var_def.get("required", True):
            if name not in [item["title"] for item in cleaned]:
                # Si falta, lo añadimos explícitamente con answer = None
                cleaned.append({"title": name, "answer": None})

    return cleaned


def _normalize_number(value: Any) -> Optional[float]:
    """
    Intenta normalizar un número que puede venir como string con coma o punto.
    Ejemplos:
    - '1.234,56' -> 1234.56
    - '1234,56' -> 1234.56
    - '1234.56' -> 1234.56
    """
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    if not isinstance(value, str):
        raise ResponseValidationError(f"No se puede convertir a número: {value}")

    # Eliminar espacios
    v = value.strip()
    if v.lower() in {"null", "none", "n/a", "na", "-"}:
        return None

    # Detectar formato:
    # - Ambos '.' y ',': formato europeo  '1.234,56' -> '1234.56'
    # - Solo ',': decimal europeo          '1234,56'  -> '1234.56'
    # - Solo '.': decimal estándar         '1234.56'  -> '1234.56' (sin tocar)
    has_dot = "." in v
    has_comma = "," in v

    if has_dot and has_comma:
        # El punto es separador de miles, la coma es el decimal
        v = v.replace(".", "").replace(",", ".")
    elif has_comma and not has_dot:
        # La coma es el decimal
        v = v.replace(",", ".")
    # Si solo hay punto (o ninguno), el valor ya está en formato estándar

    try:
        return float(v)
    except ValueError:
        raise ResponseValidationError(f"Valor numérico inválido: {value}")
# app/services/response_validator.py
from typing import List, Dict, Any


class ResponseValidationError(Exception):
    pass


def validate_and_clean_response(
    raw_result: List[Dict[str, Any]],
    variables: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Valida que la respuesta del modelo:
    - Sea una lista de objetos {title, answer}
    - Solo contenga titles esperados
    - Limpia y normaliza answer según el tipo de variable
    """

    # Mapa de variables por nombre para poder consultar tipo, required, etc.
    var_by_name = {v["name"]: v for v in variables}

    cleaned: List[Dict[str, Any]] = []

    if not isinstance(raw_result, list):
        raise ResponseValidationError("La respuesta no es una lista.")

    for item in raw_result:
        if not isinstance(item, dict):
            raise ResponseValidationError("Cada elemento de la respuesta debe ser un objeto JSON.")

        title = item.get("title")
        answer = item.get("answer")

        if title is None:
            raise ResponseValidationError("Falta el campo 'title' en algún elemento.")

        if title not in var_by_name:
            raise ResponseValidationError(f"Título inesperado en la respuesta: {title}")

        var_def = var_by_name[title]
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

        cleaned.append({"title": title, "answer": answer})

    # Comprobar que todos los required tienen entrada (aunque sea null)
    for name, var_def in var_by_name.items():
        if var_def.get("required", True):
            if name not in [item["title"] for item in cleaned]:
                # Si falta, lo añadimos explícitamente con answer = None
                cleaned.append({"title": name, "answer": None})

    return cleaned


def _normalize_number(value: Any) -> float:
    """
    Intenta normalizar un número que puede venir como string con coma o punto.
    Ejemplos:
    - '1.234,56' -> 1234.56
    - '1234,56' -> 1234.56
    - '1234.56' -> 1234.56
    """
    if isinstance(value, (int, float)):
        return float(value)

    if not isinstance(value, str):
        raise ResponseValidationError(f"No se puede convertir a número: {value}")

    # Eliminar espacios
    v = value.strip()

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
"""
Validación automática de campos extraídos contra reglas definidas en la config.

Cada variable en PromptConfig.variables puede tener un campo opcional:
  "validation_rule": {
      "required": true/false,         # la respuesta no puede ser null/vacío
      "regex": "^\\d{9}[A-Z]$",       # expresión regular (strings)
      "min": 0,                         # valor mínimo (numéricos)
      "max": 9999999,                   # valor máximo (numéricos)
      "allowed_values": ["A", "B"]     # lista de valores permitidos
  }

Si algún campo falla su regla, el item del resultado queda marcado con
  "validation_error": "<descripción del fallo>"
y la función devuelve True (hay fallos) para que el caller pueda transicionar
el estado de la extracción a "pending_review".
"""
from __future__ import annotations

import re
from typing import Any


def _check(rule: dict, value: Any) -> str | None:
    """Retorna un mensaje de error o None si pasa la validación."""
    if not rule:
        return None

    is_empty = value is None or str(value).strip() == ""

    if rule.get("required") and is_empty:
        return "Campo requerido vacío"

    if is_empty:
        return None  # si no es requerido y está vacío, no hay más que validar

    # Regex
    pattern = rule.get("regex")
    if pattern:
        if not re.fullmatch(pattern, str(value)):
            return f"No cumple el patrón: {pattern}"

    # Numérico: min / max
    try:
        num = float(str(value).replace(",", ".").replace(" ", ""))
        mn = rule.get("min")
        mx = rule.get("max")
        if mn is not None and num < mn:
            return f"Valor {num} por debajo del mínimo {mn}"
        if mx is not None and num > mx:
            return f"Valor {num} por encima del máximo {mx}"
    except ValueError:
        pass  # no es numérico, se ignoran min/max

    # Valores permitidos
    allowed = rule.get("allowed_values")
    if allowed and str(value) not in [str(a) for a in allowed]:
        return f"Valor no permitido. Permitidos: {allowed}"

    return None


def validate_result(variables: list[dict], result: list[dict]) -> tuple[list[dict], bool]:
    """
    Aplica las reglas de validación sobre el resultado de la extracción.

    Returns:
        (result_annotated, has_errors): result con "validation_error" añadido
        donde proceda, y bool indicando si hubo al menos un fallo.
    """
    rule_by_name = {
        v.get("name", ""): v.get("validation_rule") or {}
        for v in (variables or [])
    }

    has_errors = False
    annotated = []
    for item in result:
        title = item.get("title", "")
        rule = rule_by_name.get(title, {})
        error = _check(rule, item.get("answer"))
        if error:
            has_errors = True
            annotated.append({**item, "validation_error": error})
        else:
            annotated.append(item)

    return annotated, has_errors

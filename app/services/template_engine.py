# app/services/template_engine.py
import re
from typing import List, Dict, Any, Optional


PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*[^{}]+\s*\}\}")
_VAR_REF_RE = re.compile(r"\{\{(\w+)\}\}")


def parse_var_refs(description: str, known_names: set) -> set:
    """
    Devuelve los nombres de variables referenciadas en una descripción via {{NombreVar}},
    filtrando solo los que existen en known_names.
    """
    return {m for m in _VAR_REF_RE.findall(description or "") if m in known_names}


def build_variable_block(variables: List[Dict[str, Any]]) -> str:
    """
    Genera el bloque de texto que se insertará en el placeholder {{...}}
    a partir de la lista de variables.
    """
    lines = []
    for v in variables:
        # Ejemplo: {{NIF}} → NIF o NIE del emisor de la factura (obligatorio)
        required_text = " (obligatorio)" if v.get("required", True) else " (opcional)"
        line = f"{{{{{v['name']}}}}} → {v['description']}{required_text}"
        lines.append(line)
    return "\n".join(lines)


def build_base_prompt() -> str:
    """
    Prompt base por defecto de Centinell, con placeholder {{...}}.
    Se usa como fallback cuando no se proporciona uno desde BD.
    """
    return (
        "Eres Centinell, un sistema de extracción de información de documentos.\n"
        "Tu única función es leer el contenido del documento proporcionado y extraer "
        "valores para los campos indicados.\n"
        "No añadas explicaciones, comentarios ni texto adicional.\n\n"
        "CAMPOS A EXTRAER:\n"
        "{{VARIABLE_BLOCK}}\n\n"
        "REGLAS IMPORTANTES:\n"
        "- Si un campo no se encuentra en el documento, devuelve null como valor.\n"
        "- Nunca inventes valores.\n"
        "- Respeta las reglas de validación descritas para cada campo.\n\n"
        "FORMATO DE SALIDA:\n"
        "Devuelve EXCLUSIVAMENTE un JSON válido con esta estructura:\n"
        "[{\"title\": \"NombreVariable\", \"answer\": \"valor\", \"reasoning\": \"evidencia breve del documento\"}]\n"
        "- Si no hay evidencia suficiente para explicar el valor, usa reasoning = null\n"
        "- IMPORTANTE: No uses markdown, sin ``` ni ```json\n"
        "- Devuelve SOLO el JSON, sin texto antes ni después\n"
        "- Ejemplo correcto: [{\"title\": \"NIF\", \"answer\": \"12345678X\", \"reasoning\": \"Aparece junto a 'NIF emisor' en el encabezado\"}]\n"
        "- Ejemplo INCORRECTO: ```json [{...}] ```\n"
    )


def get_variable_placeholder_token(prompt_template: str) -> Optional[str]:
    """
    Devuelve el token placeholder {{...}} usado para inyectar variables.

    Reglas:
    - Debe existir al menos un placeholder.
    - Si hay varios, deben ser el mismo token repetido.
    """
    matches = PLACEHOLDER_PATTERN.findall(prompt_template or "")
    if not matches:
        return None

    # Mantener orden y unicidad
    unique_matches = list(dict.fromkeys(matches))
    if len(unique_matches) > 1:
        raise ValueError(
            "El base_prompt debe contener un único tipo de placeholder {{...}} para variables"
        )

    return unique_matches[0]


def build_final_prompt(
    variables: List[Dict[str, Any]],
    base_prompt: Optional[str] = None,
) -> str:
    """
    Construye el prompt final sustituyendo el placeholder {{...}}
    en el base_prompt por el bloque generado a partir de las variables.
    Si no se recibe base_prompt, usa el prompt por defecto.
    """
    prompt_template = base_prompt or build_base_prompt()
    variable_block = build_variable_block(variables)
    placeholder_token = get_variable_placeholder_token(prompt_template)
    if not placeholder_token:
        raise ValueError(
            "El base_prompt debe contener un placeholder {{...}} para insertar variables"
        )

    final_prompt = prompt_template.replace(placeholder_token, variable_block)
    return final_prompt
# app/routers/test_template.py
from fastapi import APIRouter
from app.services.template_engine import build_final_prompt

router = APIRouter(prefix="/test-template", tags=["test-template"])


@router.get("/")
async def get_test_template():
    """
    Endpoint de prueba que construye un prompt con una configuración
    de ejemplo y lo devuelve para que puedas verlo.
    """
    # Configuración de ejemplo (simula lo que vendrá de BD)
    variables = [
        {
            "name": "NIF",
            "description": "NIF o NIE del emisor de la factura",
            "required": True,
            "type": "string",
            "validation_regex": "^[0-9XYZ][0-9]{7}[A-Z]$",
            "max_length": 9,
        },
        {
            "name": "NombreEmpresa",
            "description": "Nombre legal completo de la empresa emisora",
            "required": True,
            "type": "string",
        },
        {
            "name": "ImporteTotal",
            "description": "Importe total de la factura con IVA, sólo número",
            "required": True,
            "type": "number",
        },
    ]

    final_prompt = build_final_prompt(variables)
    return {
        "variables": variables,
        "prompt": final_prompt,
    }
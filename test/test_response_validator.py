from app.services.response_validator import ResponseValidationError, validate_and_clean_response


def test_validate_number_accepts_null_literal_as_none():
    variables = [
        {
            "name": "importe",
            "description": "Importe total",
            "required": True,
            "type": "number",
        }
    ]
    raw_result = [{"title": "importe", "answer": "null"}]

    cleaned = validate_and_clean_response(raw_result, variables)

    assert cleaned == [{"title": "importe", "answer": None}]


def test_validate_number_rejects_invalid_numeric_text():
    variables = [
        {
            "name": "importe",
            "description": "Importe total",
            "required": True,
            "type": "number",
        }
    ]
    raw_result = [{"title": "importe", "answer": "abc"}]

    try:
        validate_and_clean_response(raw_result, variables)
        assert False, "Se esperaba ResponseValidationError"
    except ResponseValidationError as exc:
        assert "Valor numérico inválido" in str(exc)


def test_validate_preserves_reasoning_when_present():
    variables = [
        {
            "name": "importe",
            "description": "Importe total",
            "required": True,
            "type": "number",
        }
    ]
    raw_result = [
        {
            "title": "importe",
            "answer": "1234,56",
            "reasoning": "Se lee en el bloque 'Total factura'.",
        }
    ]

    cleaned = validate_and_clean_response(raw_result, variables)

    assert cleaned == [
        {
            "title": "importe",
            "answer": 1234.56,
            "reasoning": "Se lee en el bloque 'Total factura'.",
        }
    ]

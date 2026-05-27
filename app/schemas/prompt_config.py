# app/schemas/prompt_config.py
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from uuid import UUID

class VariableDefinition(BaseModel):
    name: str = Field(..., description="Nombre de la variable, por ejemplo 'NIF'")
    description: str = Field(..., description="Descripción del campo a extraer")
    required: bool = True
    type: str = "string"
    validation_regex: Optional[str] = None
    max_length: Optional[int] = None

class PromptConfigCreate(BaseModel):
    name: str
    description: Optional[str] = None
    base_prompt: str
    variables: List[VariableDefinition]
    model: str = "gpt-4o"
    temperature: float = 0.0

class PromptConfigRead(BaseModel):
    id: UUID
    bu_id: UUID
    name: str
    description: Optional[str]
    version: int
    base_prompt: str
    variables: List[VariableDefinition]
    model: str
    temperature: float
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
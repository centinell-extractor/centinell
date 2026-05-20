# app/db/models.py
from sqlalchemy import Column, String, Integer, Boolean, Text, JSON, TIMESTAMP, func, ForeignKey, Float, Index
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
import uuid

from app.db.connection import Base


class Collection(Base):
    __tablename__ = "collections"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    config_id = Column(PG_UUID(as_uuid=True), ForeignKey("prompt_configs.id"), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_collection_config", "config_id"),
        Index("idx_collection_created", "created_at"),
    )


class PromptConfig(Base):
    __tablename__ = "prompt_configs"

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    version = Column(Integer, nullable=False, default=1)
    base_prompt = Column(Text, nullable=False)
    variables = Column(JSON, nullable=False)
    model = Column(String(50), nullable=False, default="gpt-4o")
    temperature = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_prompt_config_active', 'is_active'),
    )


class Extraction(Base):
    __tablename__ = "extractions"

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    prompt_config_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("prompt_configs.id"),
        nullable=False
    )
    document_name = Column(String(255), nullable=True)
    document_hash = Column(String(64), nullable=True)
    collection_id = Column(PG_UUID(as_uuid=True), ForeignKey("collections.id"), nullable=True)
    prompt_sent = Column(Text, nullable=False)
    raw_llm_response = Column(Text, nullable=True)
    validated_result = Column(JSON, nullable=True)
    status = Column(String(20), nullable=False, default="pending")
    retries = Column(Integer, default=0)
    latency_ms = Column(Integer, nullable=True)
    model_used = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    
    __table_args__ = (
        Index('idx_extraction_config', 'prompt_config_id'),
        Index('idx_extraction_status', 'status'),
        Index('idx_extraction_created', 'created_at'),
        Index('idx_extraction_collection', 'collection_id'),
    )
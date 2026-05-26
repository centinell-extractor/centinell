# app/db/models.py
from sqlalchemy import Column, String, Integer, Boolean, Text, JSON, TIMESTAMP, func, ForeignKey, Float, Index, UniqueConstraint
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
    bu_id = Column(PG_UUID(as_uuid=True), ForeignKey("business_units.id", ondelete="CASCADE"), nullable=False)
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
        Index('idx_prompt_config_bu', 'bu_id'),
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
    bu_id = Column(PG_UUID(as_uuid=True), ForeignKey("business_units.id", ondelete="SET NULL"), nullable=True)
    document_id = Column(PG_UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
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
        Index('idx_extraction_bu', 'bu_id'),
        Index('idx_extraction_document', 'document_id'),
        Index('idx_extraction_status', 'status'),
        Index('idx_extraction_created', 'created_at'),
        Index('idx_extraction_collection', 'collection_id'),
    )


class Document(Base):
    __tablename__ = "documents"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bu_id = Column(PG_UUID(as_uuid=True), ForeignKey("business_units.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    filename = Column(String(255), nullable=False)
    mime_type = Column(String(120), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    sha256 = Column(String(64), nullable=False)
    storage_key = Column(String(500), nullable=False, unique=True)
    created_by = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    # Async OCR processing
    status = Column(String(20), nullable=False, default="pending")
    ocr_text = Column(Text, nullable=True)
    ocr_error = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_documents_bu_created", "bu_id", "created_at"),
        Index("idx_documents_bu_title", "bu_id", "title"),
        Index("idx_documents_status", "status"),
    )


class Assessment(Base):
    __tablename__ = "assessments"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bu_id = Column(PG_UUID(as_uuid=True), ForeignKey("business_units.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_assessment_bu", "bu_id"),
        Index("idx_assessment_active", "is_active"),
    )


class AssessmentConfig(Base):
    __tablename__ = "assessment_configs"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assessment_id = Column(PG_UUID(as_uuid=True), ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False)
    config_id = Column(PG_UUID(as_uuid=True), ForeignKey("prompt_configs.id", ondelete="CASCADE"), nullable=False)
    position = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index("idx_assessment_config_assessment", "assessment_id"),
    )


class AssessmentRun(Base):
    __tablename__ = "assessment_runs"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assessment_id = Column(PG_UUID(as_uuid=True), ForeignKey("assessments.id", ondelete="SET NULL"), nullable=True)
    assessment_name = Column(String(150), nullable=True)
    bu_id = Column(PG_UUID(as_uuid=True), ForeignKey("business_units.id", ondelete="SET NULL"), nullable=True)
    document_id = Column(PG_UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    document_name = Column(String(255), nullable=True)
    created_by = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(20), nullable=False, default="pending")
    combined_result = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_assessment_run_assessment", "assessment_id"),
        Index("idx_assessment_run_bu", "bu_id"),
        Index("idx_assessment_run_status", "status"),
        Index("idx_assessment_run_created", "created_at"),
        Index("idx_assessment_run_created_by", "created_by"),
    )


class BusinessUnit(Base):
    __tablename__ = "business_units"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    code = Column(String(40), nullable=False, unique=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class User(Base):
    __tablename__ = "users"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=False, unique=True)
    full_name = Column(String(200), nullable=True)
    password_hash = Column(Text, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    is_global_admin = Column(Boolean, nullable=False, default=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    last_login_at = Column(TIMESTAMP(timezone=True), nullable=True)


class UserBUAccess(Base):
    __tablename__ = "user_bu_access"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    bu_id = Column(PG_UUID(as_uuid=True), ForeignKey("business_units.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False, default="bu_user")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "bu_id", name="uq_user_bu_access"),
        Index("idx_user_bu_access_user", "user_id"),
        Index("idx_user_bu_access_bu", "bu_id"),
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String(64), nullable=False, unique=True)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    revoked_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_refresh_tokens_user", "user_id"),
        Index("idx_refresh_tokens_expires", "expires_at"),
    )


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bu_id = Column(PG_UUID(as_uuid=True), ForeignKey("business_units.id", ondelete="CASCADE"), nullable=False)
    created_by = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(100), nullable=False)
    key_prefix = Column(String(16), nullable=False)
    key_hash = Column(String(64), nullable=False, unique=True)
    role = Column(String(20), nullable=False, default="bu_user")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    last_used_at = Column(TIMESTAMP(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_api_keys_bu", "bu_id"),
        Index("idx_api_keys_hash", "key_hash"),
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    bu_id = Column(PG_UUID(as_uuid=True), ForeignKey("business_units.id", ondelete="SET NULL"), nullable=True)
    event_type = Column(String(80), nullable=False)
    resource_type = Column(String(80), nullable=True)
    resource_id = Column(String(80), nullable=True)
    message = Column(Text, nullable=True)
    details = Column("metadata", JSON, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_audit_events_actor", "actor_user_id"),
        Index("idx_audit_events_bu", "bu_id"),
        Index("idx_audit_events_created", "created_at"),
    )
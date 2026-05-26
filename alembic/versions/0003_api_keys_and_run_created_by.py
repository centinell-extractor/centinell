"""api_keys table and assessment_runs.created_by

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '0003'
down_revision: Union[str, Sequence[str], None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── api_keys ──────────────────────────────────────────────────
    op.create_table(
        'api_keys',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('bu_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('business_units.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('key_prefix', sa.String(16), nullable=False),
        sa.Column('key_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('role', sa.String(20), nullable=False, server_default='bu_user'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('last_used_at', sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index('idx_api_keys_bu', 'api_keys', ['bu_id'])
    op.create_index('idx_api_keys_hash', 'api_keys', ['key_hash'])

    # ── assessment_runs.created_by ────────────────────────────────
    op.add_column(
        'assessment_runs',
        sa.Column('created_by', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
    )
    op.create_index('idx_assessment_run_created_by', 'assessment_runs', ['created_by'])


def downgrade() -> None:
    op.drop_index('idx_assessment_run_created_by', table_name='assessment_runs')
    op.drop_column('assessment_runs', 'created_by')

    op.drop_index('idx_api_keys_hash', table_name='api_keys')
    op.drop_index('idx_api_keys_bu', table_name='api_keys')
    op.drop_table('api_keys')

"""api_keys table and assessment_runs.created_by

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0003'
down_revision: Union[str, Sequence[str], None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use raw SQL so each step is idempotent (init_models may have already
    # created tables/columns via create_all on the same production DB).

    op.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            id UUID PRIMARY KEY,
            bu_id UUID NOT NULL REFERENCES business_units(id) ON DELETE CASCADE,
            created_by UUID REFERENCES users(id) ON DELETE SET NULL,
            name VARCHAR(100) NOT NULL,
            key_prefix VARCHAR(16) NOT NULL,
            key_hash VARCHAR(64) NOT NULL UNIQUE,
            role VARCHAR(20) NOT NULL DEFAULT 'bu_user',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
            last_used_at TIMESTAMP WITH TIME ZONE
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_api_keys_bu ON api_keys (bu_id)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys (key_hash)
    """)

    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'assessment_runs' AND column_name = 'created_by'
            ) THEN
                ALTER TABLE assessment_runs
                    ADD COLUMN created_by UUID REFERENCES users(id) ON DELETE SET NULL;
            END IF;
        END
        $$
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_assessment_run_created_by
            ON assessment_runs (created_by)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_assessment_run_created_by")
    op.execute("""
        ALTER TABLE assessment_runs DROP COLUMN IF EXISTS created_by
    """)
    op.execute("DROP INDEX IF EXISTS idx_api_keys_hash")
    op.execute("DROP INDEX IF EXISTS idx_api_keys_bu")
    op.execute("DROP TABLE IF EXISTS api_keys")

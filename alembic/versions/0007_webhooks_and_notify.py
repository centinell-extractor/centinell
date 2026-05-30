"""webhook_configs + notify_on_completion en users

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-30 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op


revision: str = "0007"
down_revision: Union[str, Sequence[str], None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS notify_on_completion BOOLEAN NOT NULL DEFAULT false;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'webhook_configs'
            ) THEN
                CREATE TABLE webhook_configs (
                    id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
                    bu_id             UUID        NOT NULL
                                                  REFERENCES business_units(id)
                                                  ON DELETE CASCADE,
                    name              VARCHAR(150) NOT NULL,
                    url               VARCHAR(2000) NOT NULL,
                    secret            VARCHAR(128) NOT NULL,
                    events            JSONB       NOT NULL DEFAULT '[]',
                    is_active         BOOLEAN     NOT NULL DEFAULT true,
                    last_triggered_at TIMESTAMPTZ,
                    last_status_code  INTEGER,
                    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
                );

                CREATE INDEX idx_webhooks_bu     ON webhook_configs (bu_id);
                CREATE INDEX idx_webhooks_active ON webhook_configs (is_active);
            END IF;
        END $$
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS webhook_configs")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS notify_on_completion")

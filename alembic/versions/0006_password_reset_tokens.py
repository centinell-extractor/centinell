"""password_reset_tokens — tokens de un solo uso para recuperación de contraseña

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-29 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0006"
down_revision: Union[str, Sequence[str], None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'password_reset_tokens'
            ) THEN
                CREATE TABLE password_reset_tokens (
                    id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id    UUID        NOT NULL
                                           REFERENCES users(id)
                                           ON DELETE CASCADE,
                    token_hash VARCHAR(64) NOT NULL UNIQUE,
                    expires_at TIMESTAMPTZ NOT NULL,
                    used_at    TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );

                CREATE INDEX idx_prt_user    ON password_reset_tokens (user_id);
                CREATE INDEX idx_prt_expires ON password_reset_tokens (expires_at);
            END IF;
        END $$
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS password_reset_tokens")

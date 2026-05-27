"""collection.bu_id directo y assessment_runs.updated_at

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-27 00:00:00.000000

Cambios:
- collections: añade bu_id (FK → business_units) con backfill desde prompt_configs
- assessment_runs: añade updated_at para rastrear cambios de estado
"""
from typing import Sequence, Union

from alembic import op


revision: str = '0004'
down_revision: Union[str, Sequence[str], None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── collections.bu_id ────────────────────────────────────────────────────
    # 1. Añadir la columna como nullable para poder hacer el backfill.
    # 2. Rellenar desde prompt_configs (todas las colecciones existentes ya
    #    tienen un config_id válido).
    # 3. Poner NOT NULL + FK + índice.
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'collections' AND column_name = 'bu_id'
            ) THEN
                ALTER TABLE collections
                    ADD COLUMN bu_id UUID;

                UPDATE collections
                SET bu_id = (
                    SELECT pc.bu_id
                    FROM prompt_configs pc
                    WHERE pc.id = collections.config_id
                );

                ALTER TABLE collections
                    ALTER COLUMN bu_id SET NOT NULL;

                ALTER TABLE collections
                    ADD CONSTRAINT fk_collections_bu
                    FOREIGN KEY (bu_id)
                    REFERENCES business_units(id)
                    ON DELETE CASCADE;
            END IF;
        END
        $$
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_collection_bu ON collections (bu_id)
    """)

    # ── assessment_runs.updated_at ────────────────────────────────────────────
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'assessment_runs' AND column_name = 'updated_at'
            ) THEN
                ALTER TABLE assessment_runs
                    ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT now();
            END IF;
        END
        $$
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_collection_bu")
    op.execute("""
        ALTER TABLE collections
            DROP CONSTRAINT IF EXISTS fk_collections_bu,
            DROP COLUMN IF EXISTS bu_id
    """)
    op.execute("""
        ALTER TABLE assessment_runs DROP COLUMN IF EXISTS updated_at
    """)

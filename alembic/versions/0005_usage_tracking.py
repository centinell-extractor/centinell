"""usage_events, plans y bu_plans — infraestructura de tracking de uso

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-27 00:00:00.000000

Cambios:
  - usage_events : log granular de eventos de uso por BU (uploads, extracciones,
                   tokens consumidos, exportaciones). Append-only, base de
                   cualquier informe de consumo o facturación.
  - plans        : catálogo de planes comerciales con límites configurables por
                   BU. Cuatro planes predeterminados: free, starter,
                   professional, enterprise.
  - bu_plans     : asignación de plan a BU con historial (ends_at = NULL → plan
                   activo; ends_at con fecha → plan cerrado).
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0005"
down_revision: Union[str, Sequence[str], None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── usage_events ──────────────────────────────────────────────────────────
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'usage_events'
            ) THEN
                CREATE TABLE usage_events (
                    id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
                    bu_id      UUID        NOT NULL
                                           REFERENCES business_units(id)
                                           ON DELETE CASCADE,
                    user_id    UUID        REFERENCES users(id)
                                           ON DELETE SET NULL,
                    event_type VARCHAR(64) NOT NULL,
                    quantity   BIGINT      NOT NULL DEFAULT 1,
                    metadata   JSONB,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );

                -- Índices orientados a queries de reporting
                CREATE INDEX idx_usage_events_bu_created
                    ON usage_events (bu_id, created_at DESC);
                CREATE INDEX idx_usage_events_bu_type
                    ON usage_events (bu_id, event_type);
                CREATE INDEX idx_usage_events_created
                    ON usage_events (created_at DESC);
            END IF;
        END $$
    """)

    # ── plans ─────────────────────────────────────────────────────────────────
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'plans'
            ) THEN
                CREATE TABLE plans (
                    id                        UUID        PRIMARY KEY
                                                          DEFAULT gen_random_uuid(),
                    code                      VARCHAR(40) NOT NULL UNIQUE,
                    display_name              VARCHAR(128) NOT NULL,
                    max_docs_per_month        INTEGER,
                    max_extractions_per_month INTEGER,
                    max_tokens_per_month      BIGINT,
                    max_users                 INTEGER,
                    price_monthly_cents       INTEGER     NOT NULL DEFAULT 0,
                    is_active                 BOOLEAN     NOT NULL DEFAULT true,
                    created_at                TIMESTAMPTZ NOT NULL DEFAULT now()
                );

                -- Planes predeterminados. Ajustar según modelo comercial.
                INSERT INTO plans (
                    code, display_name,
                    max_docs_per_month, max_extractions_per_month,
                    max_tokens_per_month, max_users,
                    price_monthly_cents
                ) VALUES
                    ('free',         'Gratuito',      50,    100,    200000,    3,   0),
                    ('starter',      'Starter',       500,   1000,   2000000,   10,  4900),
                    ('professional', 'Professional',  5000,  10000,  20000000,  50,  19900),
                    ('enterprise',   'Enterprise',    NULL,  NULL,   NULL,      NULL, 99900);
            END IF;
        END $$
    """)

    # ── bu_plans ──────────────────────────────────────────────────────────────
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'bu_plans'
            ) THEN
                CREATE TABLE bu_plans (
                    id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
                    bu_id      UUID        NOT NULL
                                           REFERENCES business_units(id)
                                           ON DELETE CASCADE,
                    plan_id    UUID        NOT NULL
                                           REFERENCES plans(id),
                    starts_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                    ends_at    TIMESTAMPTZ,
                    created_by UUID        REFERENCES users(id)
                                           ON DELETE SET NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );

                CREATE INDEX idx_bu_plans_bu
                    ON bu_plans (bu_id);
                -- Índice parcial para localizar el plan activo (ends_at IS NULL)
                CREATE INDEX idx_bu_plans_active
                    ON bu_plans (bu_id, starts_at DESC)
                    WHERE ends_at IS NULL;
            END IF;
        END $$
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS bu_plans")
    op.execute("DROP TABLE IF EXISTS plans")
    op.execute("DROP TABLE IF EXISTS usage_events")

"""Seed 4 billing plans

Revision ID: 0008
Revises: 0746a5e3984a
Create Date: 2026-06-08 22:26:00.000000

"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0008'
down_revision: Union[str, Sequence[str], None] = '0746a5e3984a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Seed the 4 billing plans (prices in euro cents)."""
    # Using raw SQL to avoid issues with bulk_insert and ON CONFLICT
    # Prices: free=0€, starter=19€, business=79€, enterprise=contactar
    # Overages: starter(0.20€/doc, 0.10€/ext, 5€/user), business(0.15€/doc, 0.08€/ext, 3€/user)
    op.execute("""
    INSERT INTO plans (id, code, display_name, max_docs_per_month, max_extractions_per_month,
                       max_tokens_per_month, max_users, price_monthly_cents, allow_overage,
                       overage_doc_cents, overage_extraction_cents, overage_user_cents, is_active)
    VALUES
        (gen_random_uuid(), 'free', 'Gratuito', 10, 20, NULL, 1, 0, false, 0, 0, 0, true),
        (gen_random_uuid(), 'starter', 'Starter', 100, 200, NULL, 3, 1900, true, 20, 10, 500, true),
        (gen_random_uuid(), 'business', 'Business', 1000, 2500, NULL, 20, 7900, true, 15, 8, 300, true),
        (gen_random_uuid(), 'enterprise', 'Enterprise', NULL, NULL, NULL, NULL, 0, false, 0, 0, 0, true)
    ON CONFLICT (code) DO NOTHING;
    """)


def downgrade() -> None:
    """Remove seeded plans."""
    op.execute("DELETE FROM plans WHERE code IN ('free', 'starter', 'business', 'enterprise')")

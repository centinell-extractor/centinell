"""add billing tables and plan overage fields

Revision ID: 0746a5e3984a
Revises: 0007
Create Date: 2026-06-08 22:25:16.620586

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0746a5e3984a'
down_revision: Union[str, Sequence[str], None] = '0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add billing fields to plans table
    op.add_column('plans', sa.Column('allow_overage', sa.Boolean(), server_default='true', nullable=False))
    op.add_column('plans', sa.Column('overage_doc_cents', sa.Integer(), server_default='20', nullable=False))
    op.add_column('plans', sa.Column('overage_extraction_cents', sa.Integer(), server_default='10', nullable=False))
    op.add_column('plans', sa.Column('overage_user_cents', sa.Integer(), server_default='500', nullable=False))

    # Create invoices table
    op.create_table('invoices',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('bu_id', sa.UUID(), nullable=False),
        sa.Column('period_month', sa.Date(), nullable=False),
        sa.Column('plan_id', sa.UUID(), nullable=True),
        sa.Column('plan_price_cents', sa.Integer(), nullable=False),
        sa.Column('overage_docs', sa.Integer(), nullable=False),
        sa.Column('overage_docs_cost_cents', sa.Integer(), nullable=False),
        sa.Column('overage_extractions', sa.Integer(), nullable=False),
        sa.Column('overage_extractions_cost_cents', sa.Integer(), nullable=False),
        sa.Column('overage_users', sa.Integer(), nullable=False),
        sa.Column('overage_users_cost_cents', sa.Integer(), nullable=False),
        sa.Column('total_cents', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('paid_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['bu_id'], ['business_units.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['plan_id'], ['plans.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('bu_id', 'period_month', name='uq_invoice_bu_period')
    )
    op.create_index('idx_invoices_bu', 'invoices', ['bu_id'], unique=False)
    op.create_index('idx_invoices_period', 'invoices', ['period_month'], unique=False)
    op.create_index('idx_invoices_status', 'invoices', ['status'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_invoices_status', table_name='invoices')
    op.drop_index('idx_invoices_period', table_name='invoices')
    op.drop_index('idx_invoices_bu', table_name='invoices')
    op.drop_table('invoices')
    op.drop_column('plans', 'overage_user_cents')
    op.drop_column('plans', 'overage_extraction_cents')
    op.drop_column('plans', 'overage_doc_cents')
    op.drop_column('plans', 'allow_overage')

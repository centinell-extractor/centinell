"""add_document_status_and_ocr_text

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-25 22:18:06.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0002'
down_revision: Union[str, Sequence[str], None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('documents', sa.Column(
        'status',
        sa.String(20),
        nullable=False,
        server_default='processed',  # documentos existentes ya están procesados
    ))
    op.add_column('documents', sa.Column('ocr_text', sa.Text(), nullable=True))
    op.add_column('documents', sa.Column('ocr_error', sa.Text(), nullable=True))
    op.create_index('idx_documents_status', 'documents', ['status'])


def downgrade() -> None:
    op.drop_index('idx_documents_status', table_name='documents')
    op.drop_column('documents', 'ocr_error')
    op.drop_column('documents', 'ocr_text')
    op.drop_column('documents', 'status')

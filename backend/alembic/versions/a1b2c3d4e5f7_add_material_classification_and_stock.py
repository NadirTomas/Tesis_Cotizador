"""add material classification (type/alloy) and stock_sheets

Revision ID: a1b2c3d4e5f7
Revises: f5a6b7c8d9e0
Create Date: 2026-08-24 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f7'
down_revision: Union[str, Sequence[str], None] = 'f5a6b7c8d9e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('materials', sa.Column('material_type', sa.String(), nullable=True))
    op.add_column('materials', sa.Column('alloy', sa.String(), nullable=True))

    op.create_table(
        'stock_sheets',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('material_id', sa.Integer(), sa.ForeignKey('materials.id'), nullable=False),
        sa.Column('code', sa.String(), nullable=False),
        sa.Column('stock_type', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='AVAILABLE'),
        sa.Column('original_width_mm', sa.Float(), nullable=True),
        sa.Column('original_height_mm', sa.Float(), nullable=True),
        sa.Column('original_area_mm2', sa.Float(), nullable=False),
        sa.Column('remaining_area_mm2', sa.Float(), nullable=False),
        sa.Column('geometry', sa.JSON(), nullable=False),
        sa.Column('source_sheet_id', sa.Integer(), sa.ForeignKey('stock_sheets.id'), nullable=True),
        sa.Column('source_quotation_id', sa.Integer(), sa.ForeignKey('quotations.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.UniqueConstraint('company_id', 'code', name='uq_stock_sheet_company_code'),
    )
    op.create_index('ix_stock_sheets_company_id', 'stock_sheets', ['company_id'])
    op.create_index(
        'ix_stock_sheets_company_material_status',
        'stock_sheets',
        ['company_id', 'material_id', 'status'],
    )


def downgrade() -> None:
    op.drop_index('ix_stock_sheets_company_material_status', table_name='stock_sheets')
    op.drop_index('ix_stock_sheets_company_id', table_name='stock_sheets')
    op.drop_table('stock_sheets')
    op.drop_column('materials', 'alloy')
    op.drop_column('materials', 'material_type')

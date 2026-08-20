"""add stock_reservations, stock_movements, company remnant thresholds

Revision ID: c3d4e5f6a8b9
Revises: b2c3d4e5f6a8
Create Date: 2026-08-26 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3d4e5f6a8b9'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'companies',
        sa.Column('minimum_remnant_area_mm2', sa.Float(), server_default='2500', nullable=False),
    )
    op.add_column('companies', sa.Column('minimum_remnant_width_mm', sa.Float(), nullable=True))
    op.add_column('companies', sa.Column('minimum_remnant_height_mm', sa.Float(), nullable=True))

    op.create_table(
        'stock_reservations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('stock_sheet_id', sa.Integer(), sa.ForeignKey('stock_sheets.id'), nullable=False),
        sa.Column('piece_id', sa.Integer(), sa.ForeignKey('pieces.id'), nullable=False),
        sa.Column('quotation_id', sa.Integer(), sa.ForeignKey('quotations.id'), nullable=False),
        sa.Column('quotation_item_id', sa.Integer(), sa.ForeignKey('quotation_items.id'), nullable=True),
        sa.Column('rotation', sa.Integer(), nullable=False),
        sa.Column('x', sa.Float(), nullable=False),
        sa.Column('y', sa.Float(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='ACTIVE'),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )
    op.create_index('ix_stock_reservations_company_id', 'stock_reservations', ['company_id'])
    op.create_index('ix_stock_reservations_stock_sheet_id', 'stock_reservations', ['stock_sheet_id'])

    op.create_table(
        'stock_movements',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('stock_sheet_id', sa.Integer(), sa.ForeignKey('stock_sheets.id'), nullable=False),
        sa.Column('movement_type', sa.String(), nullable=False),
        sa.Column('quotation_id', sa.Integer(), sa.ForeignKey('quotations.id'), nullable=True),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('details', sa.JSON(), nullable=True),
    )
    op.create_index('ix_stock_movements_company_id', 'stock_movements', ['company_id'])
    op.create_index('ix_stock_movements_stock_sheet_id', 'stock_movements', ['stock_sheet_id'])


def downgrade() -> None:
    op.drop_index('ix_stock_movements_stock_sheet_id', table_name='stock_movements')
    op.drop_index('ix_stock_movements_company_id', table_name='stock_movements')
    op.drop_table('stock_movements')

    op.drop_index('ix_stock_reservations_stock_sheet_id', table_name='stock_reservations')
    op.drop_index('ix_stock_reservations_company_id', table_name='stock_reservations')
    op.drop_table('stock_reservations')

    op.drop_column('companies', 'minimum_remnant_height_mm')
    op.drop_column('companies', 'minimum_remnant_width_mm')
    op.drop_column('companies', 'minimum_remnant_area_mm2')

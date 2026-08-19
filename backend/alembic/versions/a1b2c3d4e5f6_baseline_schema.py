"""baseline schema

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-08-19 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crea el esquema inicial (tablas nunca creadas por una migración real)."""
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('email', sa.String(), nullable=False, unique=True, index=True),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
    )

    op.create_table(
        'clients',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('cuit_cuil', sa.String(), nullable=True),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('address', sa.String(), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )

    op.create_table(
        'materials',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('thickness_mm', sa.Float(), nullable=False),
        sa.Column('sheet_width_mm', sa.Float(), nullable=False),
        sa.Column('sheet_height_mm', sa.Float(), nullable=False),
        sa.Column('sheet_cost_ars', sa.Float(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )

    op.create_table(
        'machine_configs',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('material_id', sa.Integer(), sa.ForeignKey('materials.id'), nullable=False),
        sa.Column('cut_speed_mm_min', sa.Float(), nullable=False),
        sa.Column('machine_cost_per_hour_ars', sa.Float(), nullable=False),
        sa.Column('setup_time_min', sa.Float(), nullable=False),
        sa.Column('labor_percent', sa.Float(), nullable=False, server_default='30.0'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    op.create_table(
        'pieces',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('material_id', sa.Integer(), sa.ForeignKey('materials.id'), nullable=True),
        sa.Column('dxf_path', sa.String(), nullable=True),
        sa.Column('preview_path', sa.String(), nullable=True),
        sa.Column('length_cut_mm', sa.Float(), nullable=True),
        sa.Column('area_mm2', sa.Float(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )

    op.create_table(
        'quotations',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('number', sa.String(), nullable=False),
        sa.Column('client_id', sa.Integer(), sa.ForeignKey('clients.id'), nullable=False),
        sa.Column('issue_date', sa.DateTime(), nullable=False),
        sa.Column('due_date', sa.DateTime(), nullable=True),
        sa.Column('currency', sa.String(), nullable=False, server_default='ARS'),
        sa.Column('exchange_rate', sa.Float(), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='draft'),
        sa.Column('total_ars', sa.Float(), nullable=False, server_default='0'),
        sa.Column('total_usd', sa.Float(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )

    op.create_table(
        'quotation_items',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('quotation_id', sa.Integer(), sa.ForeignKey('quotations.id'), nullable=False),
        sa.Column('piece_id', sa.Integer(), sa.ForeignKey('pieces.id'), nullable=False),
        sa.Column('material_id', sa.Integer(), sa.ForeignKey('materials.id'), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('cost_material_ars', sa.Float(), nullable=False, server_default='0'),
        sa.Column('cost_machine_ars', sa.Float(), nullable=False, server_default='0'),
        sa.Column('cost_labor_ars', sa.Float(), nullable=False, server_default='0'),
        sa.Column('margin_percent', sa.Float(), nullable=False, server_default='0'),
        sa.Column('unit_price_ars', sa.Float(), nullable=False, server_default='0'),
        sa.Column('total_price_ars', sa.Float(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )

    op.create_table(
        'company_config',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('company_name', sa.String(), nullable=False),
        sa.Column('legal_name', sa.String(), nullable=True),
        sa.Column('cuit', sa.String(), nullable=True),
        sa.Column('address', sa.String(), nullable=True),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('logo_path', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )


def downgrade() -> None:
    """Elimina el esquema inicial."""
    op.drop_table('company_config')
    op.drop_table('quotation_items')
    op.drop_table('quotations')
    op.drop_table('pieces')
    op.drop_table('machine_configs')
    op.drop_table('materials')
    op.drop_table('clients')
    op.drop_table('users')

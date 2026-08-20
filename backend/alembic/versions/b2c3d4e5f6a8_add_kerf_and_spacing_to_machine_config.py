"""add kerf_mm and minimum_spacing_mm to machine_configs

Revision ID: b2c3d4e5f6a8
Revises: a1b2c3d4e5f7
Create Date: 2026-08-25 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2c3d4e5f6a8'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('machine_configs', sa.Column('kerf_mm', sa.Float(), server_default='0', nullable=False))
    op.add_column('machine_configs', sa.Column('minimum_spacing_mm', sa.Float(), server_default='0', nullable=False))


def downgrade() -> None:
    op.drop_column('machine_configs', 'minimum_spacing_mm')
    op.drop_column('machine_configs', 'kerf_mm')

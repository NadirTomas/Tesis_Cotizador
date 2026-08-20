"""rename company_config to companies, add is_active

Revision ID: b1c2d3e4f5a6
Revises: ad4a02af2953
Create Date: 2026-08-20 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, Sequence[str], None] = 'ad4a02af2953'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table('company_config', 'companies')
    op.add_column('companies', sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    op.drop_column('companies', 'is_active')
    op.rename_table('companies', 'company_config')

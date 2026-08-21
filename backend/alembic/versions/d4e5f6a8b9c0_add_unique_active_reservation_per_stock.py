"""add partial unique index: at most one ACTIVE reservation per stock_sheet

Revision ID: d4e5f6a8b9c0
Revises: c3d4e5f6a8b9
Create Date: 2026-08-27 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4e5f6a8b9c0'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Defensa en profundidad además del UPDATE condicional en el endpoint de
    # reserva: aunque un bug futuro llegara a saltarse esa validación, la
    # base de datos nunca deja existir dos reservas ACTIVE sobre la misma
    # chapa/retazo. Índice parcial, portable entre SQLite y Postgres.
    where_clause = sa.text("status = 'ACTIVE'")
    op.create_index(
        'uq_stock_reservations_active_stock_sheet',
        'stock_reservations',
        ['stock_sheet_id'],
        unique=True,
        sqlite_where=where_clause,
        postgresql_where=where_clause,
    )


def downgrade() -> None:
    op.drop_index('uq_stock_reservations_active_stock_sheet', table_name='stock_reservations')

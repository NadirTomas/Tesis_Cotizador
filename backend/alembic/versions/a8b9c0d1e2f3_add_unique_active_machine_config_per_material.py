"""add partial unique index: at most one active MachineConfig per material

Misma defensa en profundidad que ya tiene uq_stock_reservations_active_stock_sheet
(d4e5f6a8b9c0): _has_active_config en routes_machine_configs.py protege la
invariante "una config activa por material" solo con lectura-luego-escritura
sin lock, así que reactivar dos configs del mismo material casi al mismo
tiempo podía violarla. Verificado contra producción antes de esta migración
que no existen duplicados activos hoy (0 filas), así que el índice se puede
crear sin conflicto.

Revision ID: a8b9c0d1e2f3
Revises: f6a8b9c0d1e2
Create Date: 2026-08-26 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a8b9c0d1e2f3'
down_revision: Union[str, Sequence[str], None] = 'f6a8b9c0d1e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEX_NAME = 'uq_machine_configs_active_per_material'
_WHERE = sa.text("active = true")
_SQLITE_WHERE = sa.text("active = 1")


def upgrade() -> None:
    # sqlite_where/postgresql_where son mutuamente excluyentes en cómo los
    # renderiza cada dialecto -- no hace falta bifurcar a mano por
    # bind.dialect.name, SQLAlchemy elige el que corresponda solo.
    op.create_index(
        _INDEX_NAME,
        'machine_configs',
        ['company_id', 'material_id'],
        unique=True,
        sqlite_where=_SQLITE_WHERE,
        postgresql_where=_WHERE,
    )


def downgrade() -> None:
    op.drop_index(_INDEX_NAME, table_name='machine_configs')

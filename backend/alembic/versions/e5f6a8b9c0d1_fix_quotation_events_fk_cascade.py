"""fix quotation_events.quotation_id FK to cascade on delete

La FK original (creada en f5a6b7c8d9e0, inline vía sa.ForeignKey sin
ondelete) no tenía ON DELETE CASCADE. Como toda cotización guarda al menos
un QuotationEvent "created" desde su alta, DELETE /quotations/{id} fallaba
siempre en PostgreSQL para cotizaciones en draft (ForeignKeyViolation) —
invisible en los tests porque corren contra SQLite, que no enforce foreign
keys por defecto (ver también el cambio en app/db/session.py que habilita
PRAGMA foreign_keys=ON para que este tipo de error deje de quedar oculto).

El cascade a nivel de ORM (Quotation.events, cascade="all, delete-orphan",
agregado en el modelo junto con esta migración) ya cubre el borrado hecho
a través de SQLAlchemy. Esta migración corrige además la constraint real
en la base de datos, para que el borrado sea correcto ante cualquier
DELETE que no pase por el ORM — misma defensa en profundidad que ya usa el
resto del sistema (ej. el índice único parcial de stock_reservations).

Revision ID: e5f6a8b9c0d1
Revises: d4e5f6a8b9c0
Create Date: 2026-08-25 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5f6a8b9c0d1'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a8b9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Nombre real que Postgres asignó automáticamente a la FK sin nombre
# explícito creada en f5a6b7c8d9e0 (confirmado contra pg_constraint en la
# base de producción antes de escribir esta migración).
_PG_ORIGINAL_FK_NAME = 'quotation_events_quotation_id_fkey'
_NEW_FK_NAME = 'fk_quotation_events_quotation_id'


def _copy_from_table() -> sa.Table:
    """
    Definición de columnas de quotation_events tal como quedan hoy, usada
    solo como punto de partida para la reconstrucción de la tabla en
    SQLite (ver upgrade/downgrade). SQLite no soporta ALTER de constraints
    fuera de modo batch, y la FK original —creada inline en
    op.create_table sin nombre— no se puede reflejar por nombre para
    dropearla individualmente como sí se puede en Postgres (que la
    autonombra). Se declara aquí explícitamente created_by_id -> users
    para que la reconstrucción no la pierda: pasar copy_from reemplaza la
    reflexión automática por completo, así que cualquier columna/FK que no
    se liste acá desaparecería de la tabla recreada.
    """
    meta = sa.MetaData()
    return sa.Table(
        'quotation_events', meta,
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('quotation_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=False),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.drop_constraint(_PG_ORIGINAL_FK_NAME, 'quotation_events', type_='foreignkey')
        op.create_foreign_key(
            _NEW_FK_NAME, 'quotation_events', 'quotations',
            ['quotation_id'], ['id'], ondelete='CASCADE',
        )
    else:
        with op.batch_alter_table(
            'quotation_events', copy_from=_copy_from_table(), recreate='always'
        ) as batch_op:
            batch_op.create_foreign_key(
                _NEW_FK_NAME, 'quotations', ['quotation_id'], ['id'], ondelete='CASCADE',
            )
            batch_op.create_index('ix_quotation_events_quotation_id', ['quotation_id'])


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.drop_constraint(_NEW_FK_NAME, 'quotation_events', type_='foreignkey')
        op.create_foreign_key(
            _PG_ORIGINAL_FK_NAME, 'quotation_events', 'quotations',
            ['quotation_id'], ['id'],
        )
    else:
        with op.batch_alter_table(
            'quotation_events', copy_from=_copy_from_table(), recreate='always'
        ) as batch_op:
            batch_op.create_foreign_key(
                _PG_ORIGINAL_FK_NAME, 'quotations', ['quotation_id'], ['id'],
            )
            batch_op.create_index('ix_quotation_events_quotation_id', ['quotation_id'])

"""fix stock_reservations.quotation_item_id FK to SET NULL on delete

Mismo patrón de bug que e5f6a8b9c0d1, en otra relación: la FK original
(sin ondelete) impedía borrar un QuotationItem que tuviera alguna
StockReservation asociada (incluso ya RELEASED — la fila de la reserva no
se borra, solo cambia de estado), porque routes_quotation_items.py sí
soporta borrar un ítem en estado 'accepted' liberando su reserva primero,
pero nunca borra la fila de StockReservation en sí (es auditoría, debe
sobrevivir). Quedó invisible por la misma razón que el bug de
quotation_events: los tests corren contra SQLite, que no enforce foreign
keys por defecto — recién se hizo visible al activar
PRAGMA foreign_keys=ON (ver app/db/session.py).

SET NULL en vez de CASCADE: quotation_item_id ya es nullable=True, y una
StockReservation es un registro de auditoría de qué pasó con una chapa/
retazo físico — debe sobrevivir al ítem de cotización que la originó, solo
pierde la referencia a un ítem que ya no existe (igual que un `created_by`
que sobrevive aunque se borre el usuario, ver stock_reservations.
created_by_id, nullable=True sin relación con este cambio).

Revision ID: f6a8b9c0d1e2
Revises: e5f6a8b9c0d1
Create Date: 2026-08-25 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f6a8b9c0d1e2'
down_revision: Union[str, Sequence[str], None] = 'e5f6a8b9c0d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PG_ORIGINAL_FK_NAME = 'stock_reservations_quotation_item_id_fkey'
_NEW_FK_NAME = 'fk_stock_reservations_quotation_item_id'

# Índice único parcial creado en d4e5f6a8b9c0 — se recrea igual en ambas
# ramas para no perderlo al reconstruir la tabla en SQLite (ver comentario
# de _copy_from_table).
_ACTIVE_RESERVATION_INDEX = 'uq_stock_reservations_active_stock_sheet'
_ACTIVE_WHERE = sa.text("status = 'ACTIVE'")


def _copy_from_table() -> sa.Table:
    """
    Columnas de stock_reservations tal como quedan hoy. Igual que en
    e5f6a8b9c0d1: copy_from reemplaza la reflexión automática por
    completo en SQLite, así que toda columna/FK que no se liste acá
    desaparecería de la tabla recreada — se listan explícitamente todas
    las FK existentes (compañía, chapa, pieza, cotización, usuario) para
    no perder ninguna, no solo la que se está corrigiendo.
    """
    meta = sa.MetaData()
    return sa.Table(
        'stock_reservations', meta,
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('stock_sheet_id', sa.Integer(), sa.ForeignKey('stock_sheets.id'), nullable=False),
        sa.Column('piece_id', sa.Integer(), sa.ForeignKey('pieces.id'), nullable=False),
        sa.Column('quotation_id', sa.Integer(), sa.ForeignKey('quotations.id'), nullable=False),
        # quotation_item_id se declara SIN ForeignKey acá a propósito: es
        # justamente la FK que upgrade()/downgrade() agregan después con
        # el ondelete correcto para cada rama. La COLUMNA sí tiene que
        # estar en este copy_from (a diferencia de agregarla con
        # add_column, que la trataría como nueva y no copiaría los datos
        # existentes desde la tabla real).
        sa.Column('quotation_item_id', sa.Integer(), nullable=True),
        sa.Column('rotation', sa.Integer(), nullable=False),
        sa.Column('x', sa.Float(), nullable=False),
        sa.Column('y', sa.Float(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='ACTIVE'),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.drop_constraint(_PG_ORIGINAL_FK_NAME, 'stock_reservations', type_='foreignkey')
        op.create_foreign_key(
            _NEW_FK_NAME, 'stock_reservations', 'quotation_items',
            ['quotation_item_id'], ['id'], ondelete='SET NULL',
        )
    else:
        with op.batch_alter_table(
            'stock_reservations', copy_from=_copy_from_table(), recreate='always'
        ) as batch_op:
            batch_op.create_foreign_key(
                _NEW_FK_NAME, 'quotation_items', ['quotation_item_id'], ['id'], ondelete='SET NULL',
            )
            batch_op.create_index('ix_stock_reservations_company_id', ['company_id'])
            batch_op.create_index('ix_stock_reservations_stock_sheet_id', ['stock_sheet_id'])
            batch_op.create_index(
                _ACTIVE_RESERVATION_INDEX, ['stock_sheet_id'], unique=True, sqlite_where=_ACTIVE_WHERE,
            )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.drop_constraint(_NEW_FK_NAME, 'stock_reservations', type_='foreignkey')
        op.create_foreign_key(
            _PG_ORIGINAL_FK_NAME, 'stock_reservations', 'quotation_items',
            ['quotation_item_id'], ['id'],
        )
    else:
        with op.batch_alter_table(
            'stock_reservations', copy_from=_copy_from_table(), recreate='always'
        ) as batch_op:
            batch_op.create_foreign_key(
                _PG_ORIGINAL_FK_NAME, 'quotation_items', ['quotation_item_id'], ['id'],
            )
            batch_op.create_index('ix_stock_reservations_company_id', ['company_id'])
            batch_op.create_index('ix_stock_reservations_stock_sheet_id', ['stock_sheet_id'])
            batch_op.create_index(
                _ACTIVE_RESERVATION_INDEX, ['stock_sheet_id'], unique=True, sqlite_where=_ACTIVE_WHERE,
            )

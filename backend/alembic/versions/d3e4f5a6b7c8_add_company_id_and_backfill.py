"""add company_id to clients/materials/machine_configs/pieces/quotations + backfill

Migra el esquema de una sola empresa global a multiempresa. Si ya existían
datos, se asocian todos a la primera empresa disponible (la que ya estaba en
companies, ex-company_config) y todo usuario existente queda como OWNER de
esa empresa — es el equivalente más seguro al acceso total que ya tenían.
No se hardcodea "Cortesar S.A." ni ningún nombre: se reutiliza lo que ya
exista, o se crea un placeholder solo si la tabla companies está vacía.

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-08-20 10:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd3e4f5a6b7c8'
down_revision: Union[str, Sequence[str], None] = 'c2d3e4f5a6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ["clients", "materials", "machine_configs", "pieces", "quotations"]


def upgrade() -> None:
    for t in TABLES:
        op.add_column(t, sa.Column('company_id', sa.Integer(), nullable=True))

    bind = op.get_bind()

    row = bind.execute(sa.text("SELECT id FROM companies ORDER BY id ASC LIMIT 1")).first()
    if row:
        company_id = row[0]
    else:
        bind.execute(sa.text(
            "INSERT INTO companies (company_name, is_active, created_at, updated_at) "
            "VALUES ('CotizaLaser', TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ))
        company_id = bind.execute(sa.text("SELECT id FROM companies ORDER BY id DESC LIMIT 1")).scalar()

    for t in TABLES:
        bind.execute(
            sa.text(f"UPDATE {t} SET company_id = :cid WHERE company_id IS NULL"),
            {"cid": company_id},
        )

    users = bind.execute(sa.text("SELECT id FROM users")).fetchall()
    for (user_id,) in users:
        bind.execute(
            sa.text(
                "INSERT INTO company_members (company_id, user_id, role, is_active, created_at) "
                "VALUES (:cid, :uid, 'owner', TRUE, CURRENT_TIMESTAMP)"
            ),
            {"cid": company_id, "uid": user_id},
        )

    for t in TABLES:
        op.alter_column(t, 'company_id', nullable=False)
        op.create_index(f'ix_{t}_company_id', t, ['company_id'])
        op.create_foreign_key(f'fk_{t}_company_id', t, 'companies', ['company_id'], ['id'])

    op.create_unique_constraint('uq_quotation_company_number', 'quotations', ['company_id', 'number'])


def downgrade() -> None:
    op.drop_constraint('uq_quotation_company_number', 'quotations', type_='unique')
    for t in TABLES:
        op.drop_constraint(f'fk_{t}_company_id', t, type_='foreignkey')
        op.drop_index(f'ix_{t}_company_id', table_name=t)
        op.drop_column(t, 'company_id')

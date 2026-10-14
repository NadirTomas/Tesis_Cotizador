"""create delivery notes (remitos) and document sequences

Solo agrega tablas nuevas: no toca ninguna tabla ni dato existente.

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
Create Date: 2026-10-14 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b9c0d1e2f3a4'
down_revision: Union[str, Sequence[str], None] = 'a8b9c0d1e2f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'document_sequences',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('doc_type', sa.String(), nullable=False),
        sa.Column('last_number', sa.Integer(), nullable=False, server_default='0'),
        sa.UniqueConstraint('company_id', 'doc_type', name='uq_document_sequence_company_type'),
    )
    op.create_index('ix_document_sequences_id', 'document_sequences', ['id'])

    op.create_table(
        'delivery_notes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('quotation_id', sa.Integer(), sa.ForeignKey('quotations.id'), nullable=False),
        sa.Column('client_id', sa.Integer(), sa.ForeignKey('clients.id'), nullable=False),
        sa.Column('number', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='DRAFT'),
        sa.Column('issue_date', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('quotation_number', sa.String(), nullable=False),
        sa.Column('client_name', sa.String(), nullable=False),
        sa.Column('client_tax_id', sa.String(), nullable=True),
        sa.Column('client_address', sa.String(), nullable=True),
        sa.Column('issued_at', sa.DateTime(), nullable=True),
        sa.Column('issued_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('voided_at', sa.DateTime(), nullable=True),
        sa.Column('voided_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('void_reason', sa.String(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.UniqueConstraint('company_id', 'number', name='uq_delivery_note_company_number'),
        sa.CheckConstraint("status IN ('DRAFT', 'ISSUED', 'VOIDED')", name='ck_delivery_note_status'),
    )
    op.create_index('ix_delivery_notes_id', 'delivery_notes', ['id'])
    op.create_index('ix_delivery_notes_company_quotation', 'delivery_notes', ['company_id', 'quotation_id'])

    op.create_table(
        'delivery_note_items',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('delivery_note_id', sa.Integer(), sa.ForeignKey('delivery_notes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('quotation_item_id', sa.Integer(), sa.ForeignKey('quotation_items.id'), nullable=False),
        sa.Column('piece_id', sa.Integer(), sa.ForeignKey('pieces.id'), nullable=True),
        sa.Column('piece_name', sa.String(), nullable=False),
        sa.Column('piece_description', sa.String(), nullable=True),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('unit', sa.String(), nullable=False, server_default='un'),
        sa.UniqueConstraint('delivery_note_id', 'quotation_item_id', name='uq_delivery_note_item_line'),
        sa.CheckConstraint('quantity > 0', name='ck_delivery_note_item_quantity_positive'),
    )
    op.create_index('ix_delivery_note_items_id', 'delivery_note_items', ['id'])
    op.create_index('ix_delivery_note_items_delivery_note_id', 'delivery_note_items', ['delivery_note_id'])
    op.create_index('ix_delivery_note_items_quotation_item_id', 'delivery_note_items', ['quotation_item_id'])


def downgrade() -> None:
    op.drop_index('ix_delivery_note_items_quotation_item_id', table_name='delivery_note_items')
    op.drop_index('ix_delivery_note_items_delivery_note_id', table_name='delivery_note_items')
    op.drop_index('ix_delivery_note_items_id', table_name='delivery_note_items')
    op.drop_table('delivery_note_items')
    op.drop_index('ix_delivery_notes_company_quotation', table_name='delivery_notes')
    op.drop_index('ix_delivery_notes_id', table_name='delivery_notes')
    op.drop_table('delivery_notes')
    op.drop_index('ix_document_sequences_id', table_name='document_sequences')
    op.drop_table('document_sequences')

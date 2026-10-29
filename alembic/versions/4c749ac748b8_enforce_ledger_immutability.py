"""enforce ledger immutability

Revision ID: 4c749ac748b8
Revises: fbc039923d1d
Create Date: 2026-10-28 22:21:44.725213

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4c749ac748b8'
down_revision: Union[str, Sequence[str], None] = 'fbc039923d1d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_ledger_mutation()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION
                'Ledger entries are immutable: UPDATE and DELETE are prohibited.'
                USING ERRCODE = '55000';
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_ledger_entries_immutable
        BEFORE UPDATE OR DELETE ON ledger_entries
        FOR EACH ROW
        EXECUTE FUNCTION prevent_ledger_mutation();
    """)


def downgrade() -> None:
    op.execute("""
        DROP TRIGGER IF EXISTS trg_ledger_entries_immutable
        ON ledger_entries;
    """)

    op.execute("""
        DROP FUNCTION IF EXISTS prevent_ledger_mutation();
    """)

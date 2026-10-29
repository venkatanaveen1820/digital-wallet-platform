"""add wallet available and pending balances

Revision ID: bfd70515fe87
Revises: 341c1230b94d
Create Date: 2026-10-28 15:14:36.090104

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bfd70515fe87'
down_revision: Union[str, Sequence[str], None] = '341c1230b94d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Preserve all existing balances before removing the old column.
    op.add_column(
        "wallets",
        sa.Column(
            "available_balance",
            sa.Numeric(18, 2),
            nullable=True,
        ),
    )
    op.add_column(
        "wallets",
        sa.Column(
            "pending_balance",
            sa.Numeric(18, 2),
            nullable=False,
            server_default=sa.text("0.00"),
        ),
    )

    op.execute(
        "UPDATE wallets SET available_balance = balance"
    )

    op.alter_column(
        "wallets",
        "available_balance",
        existing_type=sa.Numeric(18, 2),
        nullable=False,
        server_default=sa.text("0.00"),
    )

    op.drop_constraint(
        "ck_wallets_balance_nonnegative",
        "wallets",
        type_="check",
    )

    op.drop_constraint(
        "ck_wallets_valid_status",
        "wallets",
        type_="check",
    )

    op.drop_column("wallets", "balance")

    op.create_check_constraint(
        "ck_wallets_available_balance_nonnegative",
        "wallets",
        "available_balance >= 0",
    )
    op.create_check_constraint(
        "ck_wallets_pending_balance_nonnegative",
        "wallets",
        "pending_balance >= 0",
    )
    op.create_check_constraint(
        "ck_wallets_valid_status",
        "wallets",
        "status IN ('ACTIVE', 'FROZEN', 'SUSPENDED', 'CLOSED')",
    )

    op.alter_column(
        "wallets",
        "status",
        existing_type=sa.String(length=10),
        type_=sa.String(length=10),
        existing_nullable=False,
    )

def downgrade() -> None:
    # Restore the former schema while preserving available balances.
    op.add_column(
        "wallets",
        sa.Column(
            "balance",
            sa.Numeric(18, 2),
            nullable=True,
        ),
    )

    op.execute(
        "UPDATE wallets SET balance = available_balance"
    )

    op.alter_column(
        "wallets",
        "balance",
        existing_type=sa.Numeric(18, 2),
        nullable=False,
        server_default=sa.text("0.00"),
    )

    op.drop_constraint(
        "ck_wallets_valid_status",
        "wallets",
        type_="check",
    )
    op.drop_constraint(
        "ck_wallets_pending_balance_nonnegative",
        "wallets",
        type_="check",
    )
    op.drop_constraint(
        "ck_wallets_available_balance_nonnegative",
        "wallets",
        type_="check",
    )

    op.create_check_constraint(
        "ck_wallets_balance_nonnegative",
        "wallets",
        "balance >= 0",
    )
    op.create_check_constraint(
        "ck_wallets_valid_status",
        "wallets",
        "status IN ('ACTIVE', 'FROZEN', 'CLOSED')",
    )

    op.drop_column("wallets", "pending_balance")
    op.drop_column("wallets", "available_balance")

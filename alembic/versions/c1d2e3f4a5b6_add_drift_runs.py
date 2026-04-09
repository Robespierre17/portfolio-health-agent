"""add_drift_runs

Revision ID: c1d2e3f4a5b6
Revises: 7d3b875dd87f
Create Date: 2026-04-09 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, Sequence[str], None] = "7d3b875dd87f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "drift_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_at", sa.DateTime(), nullable=False),
        sa.Column("feature", sa.String(50), nullable=False),
        sa.Column("psi", sa.Float(), nullable=False),
        sa.Column("baseline_n", sa.Integer(), nullable=False),
        sa.Column("current_n", sa.Integer(), nullable=False),
        sa.Column("alert", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("window_days", sa.Integer(), nullable=False),
    )
    op.create_index("ix_drift_runs_run_at", "drift_runs", ["run_at"])


def downgrade() -> None:
    op.drop_index("ix_drift_runs_run_at", table_name="drift_runs")
    op.drop_table("drift_runs")

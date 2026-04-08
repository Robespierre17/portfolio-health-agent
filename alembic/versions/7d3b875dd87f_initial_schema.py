"""initial_schema

Revision ID: 7d3b875dd87f
Revises: 
Create Date: 2026-04-07 22:55:46.532504

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7d3b875dd87f'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "portfolios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("owner", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "holdings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("portfolio_id", sa.Integer(), sa.ForeignKey("portfolios.id"), nullable=False),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.UniqueConstraint("portfolio_id", "ticker", name="uq_portfolio_ticker"),
    )

    op.create_table(
        "prices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("price_date", sa.Date(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.UniqueConstraint("ticker", "price_date", name="uq_ticker_date"),
    )
    op.create_index("ix_prices_ticker", "prices", ["ticker"])

    op.create_table(
        "health_scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("portfolio_id", sa.Integer(), sa.ForeignKey("portfolios.id"), nullable=False),
        sa.Column("scored_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("volatility", sa.Float()),
        sa.Column("max_drawdown", sa.Float()),
        sa.Column("sharpe", sa.Float()),
        sa.Column("concentration_hhi", sa.Float()),
        sa.Column("avg_correlation", sa.Float()),
    )


def downgrade() -> None:
    op.drop_table("health_scores")
    op.drop_index("ix_prices_ticker", table_name="prices")
    op.drop_table("prices")
    op.drop_table("holdings")
    op.drop_table("portfolios")

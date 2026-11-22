"""Initial schema for Kompas Kompetencji PostgreSQL persistence."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table_name in ("kompas_employees", "kompas_users", "kompas_evaluations"):
        op.create_table(
            table_name,
            sa.Column("id", sa.String(128), primary_key=True),
            sa.Column("payload", sa.Text(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )


def downgrade() -> None:
    for table_name in ("kompas_evaluations", "kompas_users", "kompas_employees"):
        op.drop_table(table_name)

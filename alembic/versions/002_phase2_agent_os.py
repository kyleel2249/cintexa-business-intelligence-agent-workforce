"""Phase 2 Agent OS tables

Revision ID: 002_phase2
Revises: 001_phase1
Create Date: 2026-09-26
"""
from alembic import op

revision = "002_phase2"
down_revision = "001_phase1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from database.models import Base
    import agent_os.models_db  # noqa: F401
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    pass

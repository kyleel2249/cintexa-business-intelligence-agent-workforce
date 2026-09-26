"""Phase 3 Knowledge Fabric tables

Revision ID: 003_phase3
Revises: 002_phase2
Create Date: 2026-09-26
"""
from alembic import op

revision = "003_phase3"
down_revision = "002_phase2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from database.models import Base
    import agent_os.models_db  # noqa: F401
    import knowledge_fabric.models_db  # noqa: F401
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    pass

"""Phase 5 Reliability

Revision ID: 005_phase5
Revises: 004_phase4
"""
from alembic import op

revision = "005_phase5"
down_revision = "004_phase4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from database.models import Base
    import agent_os.models_db  # noqa: F401
    import knowledge_fabric.models_db  # noqa: F401
    import tool_fabric.models_db  # noqa: F401
    import reliability.models_db  # noqa: F401
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    pass

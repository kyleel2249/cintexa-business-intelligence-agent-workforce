"""Phase 4 Tool Fabric

Revision ID: 004_phase4
Revises: 003_phase3
"""
from alembic import op

revision = "004_phase4"
down_revision = "003_phase3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from database.models import Base
    import agent_os.models_db  # noqa: F401
    import knowledge_fabric.models_db  # noqa: F401
    import tool_fabric.models_db  # noqa: F401
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    pass

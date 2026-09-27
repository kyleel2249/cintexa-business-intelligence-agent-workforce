"""Internet intelligence fabric

Revision ID: 010_inet
Revises: 009_ext
"""
from alembic import op

revision = "010_inet"
down_revision = "009_ext"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from database.models import Base
    import agent_os.models_db  # noqa: F401
    import knowledge_fabric.models_db  # noqa: F401
    import tool_fabric.models_db  # noqa: F401
    import reliability.models_db  # noqa: F401
    import observability.models_db  # noqa: F401
    import evolution.models_db  # noqa: F401
    import cintexa_platform.models_db  # noqa: F401
    import external_fabric.models_db  # noqa: F401
    import internet_fabric.models_db  # noqa: F401
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    pass

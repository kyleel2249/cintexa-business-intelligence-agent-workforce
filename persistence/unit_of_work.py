"""Unit of Work — single transaction boundary for multi-repo operations."""

from __future__ import annotations

from types import TracebackType
from typing import Optional, Type

from sqlalchemy.orm import Session, sessionmaker

from database.session import get_session_factory
from persistence.repositories import (
    AuditRepository,
    CheckpointRepository,
    ConversationRepository,
    EventRepository,
    MemoryRepository,
    MissionRepository,
    OrganisationRepository,
    TaskRepository,
    UserRepository,
    WorkflowRepository,
)


class UnitOfWork:
    def __init__(self, factory: Optional[sessionmaker] = None):
        self._factory = factory or get_session_factory()
        self.session: Optional[Session] = None
        self.organisations: Optional[OrganisationRepository] = None
        self.users: Optional[UserRepository] = None
        self.tasks: Optional[TaskRepository] = None
        self.workflows: Optional[WorkflowRepository] = None
        self.missions: Optional[MissionRepository] = None
        self.events: Optional[EventRepository] = None
        self.memories: Optional[MemoryRepository] = None
        self.checkpoints: Optional[CheckpointRepository] = None
        self.conversations: Optional[ConversationRepository] = None
        self.audits: Optional[AuditRepository] = None

    def __enter__(self) -> "UnitOfWork":
        self.session = self._factory()
        self.organisations = OrganisationRepository(self.session)
        self.users = UserRepository(self.session)
        self.tasks = TaskRepository(self.session)
        self.workflows = WorkflowRepository(self.session)
        self.missions = MissionRepository(self.session)
        self.events = EventRepository(self.session)
        self.memories = MemoryRepository(self.session)
        self.checkpoints = CheckpointRepository(self.session)
        self.conversations = ConversationRepository(self.session)
        self.audits = AuditRepository(self.session)
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        if self.session is None:
            return
        try:
            if exc_type is None:
                self.session.commit()
            else:
                self.session.rollback()
        finally:
            self.session.close()
            self.session = None

    def commit(self) -> None:
        if self.session:
            self.session.commit()

    def rollback(self) -> None:
        if self.session:
            self.session.rollback()

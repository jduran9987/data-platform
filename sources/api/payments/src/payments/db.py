"""Database wiring for SQLModel sessions."""
from __future__ import annotations

import os
from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine


def get_engine():
    """Create an engine from DATABASE_URL."""
    return create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)


ENGINE = get_engine()


def create_db_and_tables() -> None:
    """Create tables if they do not exist."""
    SQLModel.metadata.create_all(ENGINE)


def get_session() -> Generator[Session, None, None]:
    """Yield a request-scoped database session."""
    with Session(ENGINE) as session:
        yield session

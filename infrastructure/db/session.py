"""
DB engine/session setup. Defaults to a local SQLite file so the whole
stack runs with zero external setup for the hackathon demo — swap
DATABASE_URL to a real Postgres connection string for anything beyond
that (the schema doc's design has no SQLite-specific assumptions in it).
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./cargonex.db")

# check_same_thread=False is SQLite-specific (needed because FastAPI can
# use a different thread per request); harmless no-op on Postgres, but
# only pass it when actually using SQLite so a future Postgres URL
# doesn't choke on an unknown connect_arg.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db_session():
    """FastAPI dependency — yields a session, always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Creates all tables. Fine for SQLite/hackathon use; for Postgres in
    a real deployment you'd use Alembic migrations instead of this."""
    from infrastructure.db.orm_models import Base

    Base.metadata.create_all(bind=engine)

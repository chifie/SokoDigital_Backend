"""Alembic environment configuration for async SQLAlchemy.

Uses the async engine from app.database so that autogenerate can inspect
the actual database schema and compare it against our SQLAlchemy models.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

# Alembic Config object – provides access to the .ini file values
config = context.config

# Set up Python logging from the alembic.ini [loggers] section
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Import your declarative Base so autogenerate can see your models ──────────
from app.models.base import Base  # noqa: E402

target_metadata = Base.metadata


# ── Helper: do not pass a hardcoded URL from alembic.ini; use the app's config ─
def get_url() -> str:
    """Return the database URL from the application Settings."""
    from app.config import settings

    return settings.DATABASE_URL


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    With ``--sql`` flag, Alembic emits raw SQL to a file instead of executing
    it against a live database.  This is useful for generating DDL for manual
    review or for deployment scripts.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    """Helper that configures the migration context and runs pending migrations."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode against a live async database.

    Creates a temporary async engine (disposed after the migration), acquires a
    connection, and runs all pending migrations inside a transaction.
    """
    connectable = create_async_engine(get_url(), echo=False)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    """Run the async online migration."""
    asyncio.run(run_migrations_online())

from logging.config import fileConfig

from alembic import context

import app.models  # noqa: F401  registers every table on Base.metadata
from app.database import DATABASE_URL, Base, create_db_engine

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Compared against the database by `alembic revision --autogenerate`.
target_metadata = Base.metadata

# SQLite cannot alter most column properties in place. Batch mode makes
# Alembic copy the table, change the copy, and swap it in instead.
RENDER_AS_BATCH = DATABASE_URL.startswith("sqlite")


def run_migrations_offline() -> None:
    """Print the SQL instead of running it (`alembic upgrade head --sql`)."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=RENDER_AS_BATCH,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against the database at DATABASE_URL."""
    engine = create_db_engine(DATABASE_URL)

    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=RENDER_AS_BATCH,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

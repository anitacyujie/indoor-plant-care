"""Imports every feature's tables, so Base.metadata knows them all.

The app itself does not need this (each router imports its own tables);
Alembic and the migration tests do, since they compare the whole schema.
"""

import app.growing_media.models  # noqa: F401
import app.products.models  # noqa: F401

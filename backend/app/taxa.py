"""Load the taxa reference list: genera and families users pick for groups."""

from functools import lru_cache
from pathlib import Path

from app.schemas import TaxaList

TAXA_FILE = Path(__file__).parent.parent / "data" / "taxa.json"


def load_taxa(path: Path) -> TaxaList:
    """Read and validate the taxa list.

    Raises pydantic.ValidationError if the file breaks any rule, so bad data
    fails at startup instead of on a user's request.
    """
    return TaxaList.model_validate_json(path.read_text(encoding="utf-8"))


@lru_cache
def get_taxa() -> TaxaList:
    """Load the list once and reuse it; tests can override this dependency."""
    return load_taxa(TAXA_FILE)

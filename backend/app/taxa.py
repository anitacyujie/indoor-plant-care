"""Load the taxa reference list: genera and families users pick for groups."""

from pathlib import Path

from app.schemas import TaxaList

TAXA_FILE = Path(__file__).parent.parent / "data" / "taxa.json"


def load_taxa(path: Path) -> TaxaList:
    """Read and validate the taxa list.

    Raises pydantic.ValidationError if the file breaks any rule, so bad data
    fails at startup instead of on a user's request.
    """
    return TaxaList.model_validate_json(path.read_text(encoding="utf-8"))

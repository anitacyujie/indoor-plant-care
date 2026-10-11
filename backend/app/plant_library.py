import json
from pathlib import Path

from app.schemas import PlantCareGuide

PlantLibrary = dict[str, PlantCareGuide]


def load_plants(directory: Path) -> PlantLibrary:
    """Load and validate every plant JSON file in directory, keyed by plant id.

    Raises pydantic.ValidationError if any file does not match the schema,
    so bad data fails at startup instead of on a user's request.
    """
    library: PlantLibrary = {}
    for path in sorted(directory.glob("*.json")):
        guide = PlantCareGuide.model_validate_json(path.read_text(encoding="utf-8"))
        if guide.id in library:
            raise ValueError(f"duplicate plant id {guide.id!r} in {path.name}")
        library[guide.id] = guide
    return library

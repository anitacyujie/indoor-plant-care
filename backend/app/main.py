from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException

from app.plant_library import PlantLibrary, load_plants
from app.schemas import PlantCareGuide

PLANTS_DIR = Path(__file__).parent.parent / "data" / "plants"


@lru_cache
def get_plant_library() -> PlantLibrary:
    """Load the library once and reuse it; tests override this dependency."""
    return load_plants(PLANTS_DIR)


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_plant_library()  # fail fast at startup if any plant file is invalid
    yield


app = FastAPI(title="Plant Care API", lifespan=lifespan)

Library = Annotated[PlantLibrary, Depends(get_plant_library)]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/plants")
def list_plants(library: Library) -> list[PlantCareGuide]:
    return list(library.values())


@app.get("/plants/{plant_id}")
def get_plant(plant_id: str, library: Library) -> PlantCareGuide:
    if plant_id not in library:
        raise HTTPException(status_code=404, detail=f"Plant {plant_id!r} not found")
    return library[plant_id]

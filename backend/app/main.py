from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.growing_media.router import router as growing_media_router
from app.label_reading.router import router as label_reading_router
from app.products.router import router as products_router
from app.taxa.loader import get_taxa


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_taxa()  # fail fast at startup if taxa.json breaks any rule
    yield


app = FastAPI(title="Plant Care API", lifespan=lifespan)
app.include_router(products_router)
app.include_router(label_reading_router)
app.include_router(growing_media_router)


@app.get("/health")
def health():
    return {"status": "ok"}

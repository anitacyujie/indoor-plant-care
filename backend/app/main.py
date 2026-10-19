from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.routers import growing_media, products
from app.taxa import get_taxa


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_taxa()  # fail fast at startup if taxa.json breaks any rule
    yield


app = FastAPI(title="Plant Care API", lifespan=lifespan)
app.include_router(products.router)
app.include_router(growing_media.router)


@app.get("/health")
def health():
    return {"status": "ok"}

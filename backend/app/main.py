from fastapi import FastAPI

app = FastAPI(title="Plant Care API")


@app.get("/health")
def health():
    return {"status": "ok"}

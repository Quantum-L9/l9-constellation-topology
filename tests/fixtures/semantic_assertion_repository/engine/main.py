"""Fixture FastAPI surface observed by the repository-model producer."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="l9-assertion-fixture-service")


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.post("/v1/execute")
async def execute(payload: dict) -> JSONResponse:
    """Primary action endpoint."""
    action = payload.get("action")
    # TODO: route to the engine handler
    return JSONResponse({"status": "ok", "action": action})


@app.get("/v1/describe")
async def describe() -> JSONResponse:
    return JSONResponse({"actions": ["execute", "describe"]})

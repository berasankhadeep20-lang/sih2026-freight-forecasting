from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import ports, queries, routes, vessel_classes
from infrastructure.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # creates tables if they don't exist; does not seed data
    yield


app = FastAPI(
    title="CargoNex — Intelligent Freight Forecasting Model",
    description="SIH 2026 — PS 26006",
    version="0.1.0",
    lifespan=lifespan,
)


# Without this, the frontend (running on a different port during dev, and
# a different origin entirely once deployed) can't call this API from a
# browser at all — the request is blocked by the browser's CORS policy
# before it even reaches these routers. Wide open ("*") is fine for a
# hackathon demo; tighten to the actual deployed frontend origin before
# using this beyond that.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ports.router)
app.include_router(vessel_classes.router)
app.include_router(routes.router)
app.include_router(queries.router)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}

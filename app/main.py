from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.config import settings
from app.models import AnalysisRequest, AnalysisResponse, HealthResponse
from app.services.agent import ProductSearchAgent
from app.services.source_registry import SourceRegistry

BASE_DIR = Path(__file__).resolve().parent
registry = SourceRegistry(BASE_DIR / 'data' / 'sources.json')
agent = ProductSearchAgent(registry)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        yield
    finally:
        await agent.close()


app = FastAPI(title=settings.app_name, lifespan=lifespan)


@app.get('/')
async def root() -> dict:
    return {'service': settings.app_name, 'status': 'ok'}


@app.get('/sources')
async def list_sources(include_disabled: bool = False) -> list[dict]:
    return [source.__dict__ for source in registry.list_sources(include_disabled=include_disabled)]


@app.get('/health/llm', response_model=HealthResponse)
async def health_llm() -> HealthResponse:
    payload = await agent.llm.health()
    return HealthResponse(llm_available=bool(payload.get('available')), model=settings.ollama_model, details=payload)


@app.post('/analyze', response_model=AnalysisResponse)
async def analyze(request: AnalysisRequest) -> AnalysisResponse:
    return await agent.analyze(
        product_name=request.product_name,
        max_results_per_source=request.max_results_per_source,
        include_disabled=request.include_disabled,
    )

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AnalysisRequest(BaseModel):
    product_name: str = Field(min_length=1)
    max_results_per_source: int = Field(default=3, ge=1, le=10)
    include_disabled: bool = False
    product_context: str = ""


class FactBlock(BaseModel):
    amount: str = ""
    amount_kind: Literal['price', 'contract_amount', 'budget', 'registry_only', 'unknown', 'none'] = 'none'
    currency: str = ""
    brand: str = ""
    availability: str = ""
    supplier: str = ""
    buyer: str = ""
    registry_number: str = ""
    product_type: str = ""
    key_specs: list[str] = Field(default_factory=list)


class CandidateEvidence(BaseModel):
    url: str
    title: str = ""
    snippet: str = ""
    source_kind: str = ""
    score: float = 0.0
    exact_match: bool = False
    relevance_reason: str = ""


class SourceResult(BaseModel):
    source_name: str
    source_category: str
    base_url: str
    modes_used: list[str]
    used_urls: list[str] = Field(default_factory=list)
    matched: bool = False
    verdict: Literal['match', 'possible', 'no_match'] = 'no_match'
    short_info: str = ""
    facts: FactBlock = Field(default_factory=FactBlock)
    confidence: int = 0
    llm_mode: Literal['ollama', 'heuristic'] = 'heuristic'
    evidences: list[CandidateEvidence] = Field(default_factory=list)
    error: str | None = None


class AnalysisResponse(BaseModel):
    product_name: str
    results: list[SourceResult]
    final_summary: str


class HealthResponse(BaseModel):
    llm_available: bool
    model: str
    details: dict[str, Any] = Field(default_factory=dict)

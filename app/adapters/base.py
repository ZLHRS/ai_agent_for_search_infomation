from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import quote_plus

from app.core.query_expansion import build_query_signals
from app.services.source_registry import SourceConfig


@dataclass(slots=True)
class SearchRequest:
    kind: str
    url: str
    score_boost: float = 0.0
    fetch_mode: str = 'http'


@dataclass(slots=True)
class SearchPlan:
    requests: list[SearchRequest] = field(default_factory=list)


class SourceAdapter(Protocol):
    negative_signals: list[str]

    def build_search_plan(self, product_name: str, product_context: str = '') -> SearchPlan: ...

    def extract_facts(self, url: str, title: str, text: str) -> dict[str, str]: ...


class GenericSourceAdapter:
    negative_signals: list[str] = []

    def __init__(self, source: SourceConfig):
        self.source = source
        configured = list(source.negative_hints)
        adapter_specific = list(getattr(type(self), 'negative_signals', []))
        self.negative_signals = list(dict.fromkeys(configured + adapter_specific))

    def build_search_plan(self, product_name: str, product_context: str = '') -> SearchPlan:
        signals = build_query_signals(product_name, product_context)
        query = signals.search_queries[0] if signals.search_queries else product_name
        requests: list[SearchRequest] = []

        if 'source_search' in self.source.modes and self.source.search_url_template:
            requests.append(SearchRequest('source_search', self.source.search_url_template.format(query=quote_plus(query)), 1.5))
        if 'search_template' in self.source.modes and self.source.search_url_template:
            requests.append(SearchRequest('search_template', self.source.search_url_template.format(query=quote_plus(query)), 1.25))
        if 'dataset' in self.source.modes:
            requests.append(SearchRequest('dataset', self.source.base_url, 1.75))
        if 'page_only' in self.source.modes:
            requests.append(SearchRequest('page_only', self.source.base_url, 0.0))
        if 'domain_search' in self.source.modes:
            requests.append(SearchRequest('domain_search', query, 0.75))
        if 'browser' in self.source.modes:
            requests.append(SearchRequest('browser', self.source.base_url, 0.5, fetch_mode='browser'))
        return SearchPlan(requests=requests)

    def extract_facts(self, url: str, title: str, text: str) -> dict[str, str]:
        return {}

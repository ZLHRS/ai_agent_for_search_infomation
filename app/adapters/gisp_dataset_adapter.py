from __future__ import annotations

import re
from urllib.parse import quote_plus

from app.adapters.base import GenericSourceAdapter, SearchPlan, SearchRequest
from app.core.query_expansion import build_query_signals


class GispRegistryAdapter(GenericSourceAdapter):
    negative_signals = [
        'государственная информационная система промышленности',
        'расширенный поиск',
        'применить фильтр',
        'реестр российской промышленной продукции',
    ]

    def build_search_plan(self, product_name: str, product_context: str = '') -> SearchPlan:
        signals = build_query_signals(product_name, product_context)
        query = signals.search_queries[0] if signals.search_queries else product_name
        return SearchPlan([
            SearchRequest('source_search', f'{self.source.base_url}?query={quote_plus(query)}', 1.6),
            SearchRequest('dataset', self.source.base_url, 1.8),
            SearchRequest('page_only', self.source.base_url, 0.1),
        ])

    def extract_facts(self, url: str, title: str, text: str) -> dict[str, str]:
        hay = f'{url} {title} {text}'
        match = re.search(r'([РP][ПP]{2}-\d{4}-\d{6})', hay)
        return {'registry_number': match.group(1)} if match else {}

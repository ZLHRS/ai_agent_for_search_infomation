from __future__ import annotations

import re
from urllib.parse import quote_plus

from app.adapters.base import GenericSourceAdapter, SearchPlan, SearchRequest
from app.core.query_expansion import build_query_signals


class MachineryTraderSourceAdapter(GenericSourceAdapter):
    negative_signals = [
        'notify me',
        'save search',
        'auction results',
        'want to watch',
    ]

    def build_search_plan(self, product_name: str, product_context: str = '') -> SearchPlan:
        signals = build_query_signals(product_name, product_context)
        query = signals.search_queries[0] if signals.search_queries else product_name
        return SearchPlan([
            SearchRequest('source_search', f'https://www.machinerytrader.com/listings/search?keywords={quote_plus(query)}', 1.8),
            SearchRequest('page_only', self.source.base_url, 0.1),
        ])

    def extract_facts(self, url: str, title: str, text: str) -> dict[str, str]:
        brand = ''
        for token in title.split():
            cleaned = re.sub(r'[^A-Z0-9\-]', '', token)
            if len(cleaned) >= 3 and cleaned == cleaned.upper():
                brand = cleaned
                break
        return {'brand': brand} if brand else {}

from __future__ import annotations

import re
from urllib.parse import quote_plus

from app.adapters.base import GenericSourceAdapter, SearchPlan, SearchRequest
from app.core.query_expansion import build_query_signals


class TedSourceAdapter(GenericSourceAdapter):
    negative_signals = [
        'eforms notice',
        'saved searches',
        'my ted',
        'latest oj s issue',
    ]

    def build_search_plan(self, product_name: str, product_context: str = '') -> SearchPlan:
        signals = build_query_signals(product_name, product_context)
        query = signals.search_queries[0] if signals.search_queries else product_name
        return SearchPlan([
            SearchRequest('source_search', f'https://ted.europa.eu/search/result?query={quote_plus(query)}', 1.6),
            SearchRequest('browser', self.source.base_url, 0.4, fetch_mode='browser'),
        ])

    def extract_facts(self, url: str, title: str, text: str) -> dict[str, str]:
        hay = f'{url} {title} {text}'
        match = re.search(r'\b\d{6}-\d{4}\b', hay)
        return {'registry_number': match.group(0)} if match else {}


class ProzorroSourceAdapter(GenericSourceAdapter):
    negative_signals = [
        'more than 10,000 results have been found',
        'download plans',
        'all filters',
        'browser-support',
    ]

    def build_search_plan(self, product_name: str, product_context: str = '') -> SearchPlan:
        signals = build_query_signals(product_name, product_context)
        query = signals.search_queries[0] if signals.search_queries else product_name
        return SearchPlan([
            SearchRequest('source_search', f'https://prozorro.gov.ua/en/search/tender?query={quote_plus(query)}', 1.7),
            SearchRequest('browser', self.source.base_url, 0.4, fetch_mode='browser'),
        ])

    def extract_facts(self, url: str, title: str, text: str) -> dict[str, str]:
        hay = f'{url} {title} {text}'
        match = re.search(r'\bUA-\d{4}-\d{2}-\d{2}-\d{6}-[a-z]\b', hay)
        return {'registry_number': match.group(0)} if match else {}


class ZakupkiSourceAdapter(GenericSourceAdapter):
    negative_signals = [
        'реестр недобросовестных поставщиков',
        'расширенный поиск',
        'параметры поиска',
        'единая информационная система в сфере закупок',
    ]

    def build_search_plan(self, product_name: str, product_context: str = '') -> SearchPlan:
        signals = build_query_signals(product_name, product_context)
        query = signals.search_queries[0] if signals.search_queries else product_name
        return SearchPlan([
            SearchRequest('source_search', f'https://zakupki.gov.ru/epz/order/extendedsearch/results.html?searchString={quote_plus(query)}', 1.7),
            SearchRequest('browser', self.source.base_url, 0.4, fetch_mode='browser'),
        ])

    def extract_facts(self, url: str, title: str, text: str) -> dict[str, str]:
        hay = f'{url} {title} {text}'
        match = re.search(r'(?:regNumber=|извещения\s)(\d{11,22})', hay, flags=re.IGNORECASE)
        return {'registry_number': match.group(1)} if match else {}

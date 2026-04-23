from __future__ import annotations

import re
from urllib.parse import quote_plus

from app.adapters.base import GenericSourceAdapter, SearchPlan, SearchRequest
from app.core.query_expansion import build_query_signals


class RussianSoftwareRegistryAdapter(GenericSourceAdapter):
    negative_signals = [
        'tab=registry_active',
        'классификатор',
        'правообладатель',
        'поиск по реестру',
    ]

    def build_search_plan(self, product_name: str, product_context: str = '') -> SearchPlan:
        signals = build_query_signals(product_name, product_context)
        query = signals.search_queries[0] if signals.search_queries else product_name
        return SearchPlan([
            SearchRequest(
                'source_search',
                f'https://reestr.digital.gov.ru/reestr/?tab=registry_active&PROD_NAME={quote_plus(query)}&PROD_REESTR_NUM=&CLASSIFIER=&OWNER_NAME=&OWNER_INN=&OWNER_STATUS=&PROD_DES_NUM=&PROD_DES_DATE=&REQ_REG_NUM=&REQ_REG_DATE=',
                1.6,
            ),
            SearchRequest('browser', self.source.base_url, 0.4, fetch_mode='browser'),
        ])

    def extract_facts(self, url: str, title: str, text: str) -> dict[str, str]:
        match = re.search(r'№\s*([A-ZА-Я0-9\-]{4,})', f'{title} {text}')
        return {'registry_number': match.group(1)} if match else {}

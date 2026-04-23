from __future__ import annotations

from app.adapters.base import GenericSourceAdapter, SourceAdapter
from app.adapters.browser_search_adapter import ProzorroSourceAdapter, TedSourceAdapter, ZakupkiSourceAdapter
from app.adapters.company_registry_adapter import RussianSoftwareRegistryAdapter
from app.adapters.gisp_dataset_adapter import GispRegistryAdapter
from app.adapters.search_template_adapter import MachineryTraderSourceAdapter
from app.services.source_registry import SourceConfig


def get_source_adapter(source: SourceConfig) -> SourceAdapter:
    name = source.name.lower()
    domain = source.domain.lower()

    if 'ted' in name or domain.endswith('ted.europa.eu'):
        return TedSourceAdapter(source)
    if 'prozorro' in name or domain.endswith('prozorro.gov.ua'):
        return ProzorroSourceAdapter(source)
    if 'zakupki' in name or domain.endswith('zakupki.gov.ru'):
        return ZakupkiSourceAdapter(source)
    if 'machinery trader' in name or domain.endswith('machinerytrader.com'):
        return MachineryTraderSourceAdapter(source)
    if 'gisp' in name or domain.endswith('gisp.gov.ru'):
        return GispRegistryAdapter(source)
    if 'digital.gov.ru' in domain or 'software registry' in name:
        return RussianSoftwareRegistryAdapter(source)
    return GenericSourceAdapter(source)

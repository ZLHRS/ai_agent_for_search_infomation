from app.core.source_router import get_source_adapter
from app.services.source_registry import SourceConfig


def make_source(name: str, domain: str, category: str = 'tender_portal', base_url: str | None = None):
    return SourceConfig(
        name=name,
        category=category,
        base_url=base_url or f'https://{domain}/',
        domain=domain,
        enabled=True,
        modes=['source_search', 'page_only'],
    )


def test_top_sources_use_source_specific_search_urls_and_negative_signals():
    cases = [
        ('TED EU', 'ted.europa.eu', 'tender_portal', 'https://ted.europa.eu/en/', 'https://ted.europa.eu/search/result', 'eforms notice'),
        ('Prozorro', 'prozorro.gov.ua', 'tender_portal', 'https://prozorro.gov.ua/', 'https://prozorro.gov.ua/en/search/tender', 'more than 10,000 results have been found'),
        ('Zakupki', 'zakupki.gov.ru', 'tender_portal', 'https://zakupki.gov.ru/epz/order/extendedsearch/results.html', 'https://zakupki.gov.ru/epz/order/extendedsearch/results.html', 'реестр недобросовестных поставщиков'),
        ('Machinery Trader', 'machinerytrader.com', 'marketplace', 'https://www.machinerytrader.com/', 'https://www.machinerytrader.com/listings/search', 'notify me'),
        ('GISP products', 'gisp.gov.ru', 'product_registry', 'https://gisp.gov.ru/pp719v2/pub/prod/', 'https://gisp.gov.ru/pp719v2/pub/prod/', 'государственная информационная система промышленности'),
    ]

    for name, domain, category, base_url, expected_prefix, expected_negative in cases:
        adapter = get_source_adapter(make_source(name, domain, category=category, base_url=base_url))
        plan = adapter.build_search_plan(product_name='generator', product_context='diesel genset standby power')
        assert plan.requests, name
        assert plan.requests[0].url.startswith(expected_prefix), name
        assert all('duckduckgo' not in request.url for request in plan.requests), name
        assert expected_negative in adapter.negative_signals, name


def test_source_specific_extractors_pull_identifiers_from_pages():
    cases = [
        (
            make_source('TED EU', 'ted.europa.eu', base_url='https://ted.europa.eu/en/'),
            'https://ted.europa.eu/en/notice/-/detail/123456-2026',
            'Supply of diesel generator 500 kVA',
            'Notice 123456-2026 TED reference 2026/S 081-123456 CPV 31120000',
            {'registry_number': '123456-2026'},
        ),
        (
            make_source('Prozorro', 'prozorro.gov.ua', base_url='https://prozorro.gov.ua/'),
            'https://prozorro.gov.ua/tender/UA-2026-04-23-000482-a',
            'Квадрокоптер DJI Mavic 3T Advanced',
            'ID: UA-2026-04-23-000482-a Expected value 5 849 792,00 UAH',
            {'registry_number': 'UA-2026-04-23-000482-a'},
        ),
        (
            make_source('Zakupki', 'zakupki.gov.ru', base_url='https://zakupki.gov.ru/epz/order/extendedsearch/results.html'),
            'https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0873400003925000872',
            'Поставка дизель-генератора',
            'Реестровый номер извещения 0873400003925000872',
            {'registry_number': '0873400003925000872'},
        ),
        (
            make_source('Machinery Trader', 'machinerytrader.com', category='marketplace', base_url='https://www.machinerytrader.com/'),
            'https://www.machinerytrader.com/listing/for-sale/123/example',
            'CATERPILLAR XQ500 Generator',
            'Serial Number CATXQ500 Hours 120 Stock Number GT-77',
            {'brand': 'CATERPILLAR'},
        ),
        (
            make_source('GISP products', 'gisp.gov.ru', category='product_registry', base_url='https://gisp.gov.ru/pp719v2/pub/prod/'),
            'https://gisp.gov.ru/pp719v2/pub/prod/123456',
            'Дизельный генератор ГТ-500',
            'Реестровая запись № РПП-2026-001234 Производитель ООО Энергия',
            {'registry_number': 'РПП-2026-001234'},
        ),
    ]

    for source, url, title, text, expected in cases:
        adapter = get_source_adapter(source)
        facts = adapter.extract_facts(url=url, title=title, text=text)
        for key, value in expected.items():
            assert facts.get(key) == value, (source.name, key, facts)

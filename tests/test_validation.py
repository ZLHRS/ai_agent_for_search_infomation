from app.services.matchers import validate_candidate
from app.services.source_registry import SourceConfig


def make_source(category='tender_portal'):
    return SourceConfig(
        name='Test',
        category=category,
        base_url='https://example.com',
        domain='example.com',
        enabled=True,
        modes=['page_only'],
    )


def test_negative_page_rejected():
    src = make_source()
    outcome = validate_candidate('ручка', src, 'Just a moment...', 'Just a moment...', 'page_only', 5.0)
    assert outcome.matched is False
    assert outcome.verdict == 'no_match'


def test_exact_phrase_accepts_match():
    src = make_source('product_registry')
    outcome = validate_candidate('ручка шариковая', src, 'Товар', 'В закупке указана ручка шариковая синяя', 'domain_search', 6.0)
    assert outcome.matched is True
    assert outcome.verdict == 'match'


def test_company_registry_needs_exact_phrase():
    src = make_source('company_registry')
    outcome = validate_candidate('ручка', src, 'Реестр производителей', 'Перечень производителей промышленной продукции', 'page_only', 3.0)
    assert outcome.matched is False

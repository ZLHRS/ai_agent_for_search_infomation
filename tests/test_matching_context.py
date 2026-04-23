from app.services.matchers import validate_candidate
from app.services.source_registry import SourceConfig


def make_source(category='tender_portal'):
    return SourceConfig(
        name='Test',
        category=category,
        base_url='https://example.com',
        domain='example.com',
        enabled=True,
        modes=['source_search'],
    )


def test_product_context_rejects_wrong_domain_for_generic_term():
    src = make_source('marketplace')
    outcome = validate_candidate(
        product_name='generator',
        product_context='diesel generator for standby power',
        source=src,
        title='AI image generator enterprise license',
        snippet='Cloud software subscription for image generation teams',
        source_kind='source_search',
        score=6.0,
    )
    assert outcome.matched is False
    assert outcome.verdict == 'no_match'


def test_product_context_promotes_domain_synonym_match():
    src = make_source('marketplace')
    outcome = validate_candidate(
        product_name='generator',
        product_context='diesel generator genset 500 kw backup power',
        source=src,
        title='500 kW diesel genset with ATS',
        snippet='Standby power unit, low-hour machine',
        source_kind='source_search',
        score=5.0,
    )
    assert outcome.matched is True
    assert outcome.verdict == 'match'


def test_model_and_article_variants_do_not_require_exact_phrase():
    src = make_source('marketplace')
    outcome = validate_candidate(
        product_name='diesel generator DG-500',
        product_context='genset article DG-500 standby power',
        source=src,
        title='DG500 diesel genset',
        snippet='Article DG500 standby power unit with ATS',
        source_kind='source_search',
        score=5.0,
    )
    assert outcome.matched is True
    assert outcome.verdict == 'match'

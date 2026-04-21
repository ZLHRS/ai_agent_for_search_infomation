from __future__ import annotations

from dataclasses import dataclass

from app.services.source_registry import SourceConfig
from app.services.text_tools import (
    compact_text,
    contains_negative_page_signal,
    exact_phrase_present,
    extract_amount,
    is_generic_portal_page,
    token_overlap,
)


@dataclass(slots=True)
class ValidationOutcome:
    matched: bool
    verdict: str
    confidence: int
    reason: str


def validate_candidate(product_name: str, source: SourceConfig, title: str, snippet: str, source_kind: str, score: float) -> ValidationOutcome:
    title = title or ''
    snippet = snippet or ''
    hay = compact_text(f'{title} {snippet}', 2000)

    if not hay:
        return ValidationOutcome(False, 'no_match', 0, 'empty page')

    if contains_negative_page_signal(title, snippet, source.negative_hints):
        return ValidationOutcome(False, 'no_match', 0, 'negative page signal')

    exact = exact_phrase_present(product_name, snippet, title)
    hits, total = token_overlap(product_name, snippet, title)
    one_word_query = len(product_name.split()) == 1

    if source_kind.startswith('dataset:') and (exact or hits >= max(1, min(total, 2))):
        confidence = 90 if exact else 78
        return ValidationOutcome(True, 'match', confidence, 'dataset row matched product')

    if is_generic_portal_page(title, snippet) and not exact:
        return ValidationOutcome(False, 'no_match', 0, 'generic portal page without exact product mention')

    if source.category == 'company_registry' and not exact:
        return ValidationOutcome(False, 'no_match', 0, 'company registry without exact product mention')

    if exact:
        confidence = 82 if 'search_template' in source_kind or 'domain_search' in source_kind else 75
        return ValidationOutcome(True, 'match', confidence, 'exact product phrase present')

    if one_word_query:
        if hits >= 1 and score >= 4.0 and source.category in {'tender_portal', 'marketplace', 'product_registry'}:
            return ValidationOutcome(True, 'possible', 62, 'single-word query token found in focused source')
        return ValidationOutcome(False, 'no_match', 0, 'single-word query needs exact phrase or stronger evidence')

    if total and hits >= max(2, total - 1) and score >= 4.5:
        return ValidationOutcome(True, 'possible', 65, 'strong token overlap')

    return ValidationOutcome(False, 'no_match', 0, 'insufficient product evidence')


def infer_amount_kind(source_category: str, amount: str) -> str:
    if not amount:
        return 'registry_only' if source_category in {'product_registry', 'company_registry', 'open_data'} else 'none'
    if source_category in {'tender_portal', 'marketplace'}:
        return 'contract_amount'
    return 'price'

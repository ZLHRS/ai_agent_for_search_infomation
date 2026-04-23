from __future__ import annotations

from dataclasses import dataclass

from app.core.query_expansion import analyze_text
from app.services.source_registry import SourceConfig
from app.services.text_tools import (
    compact_text,
    contains_negative_page_signal,
    is_generic_portal_page,
)


@dataclass(slots=True)
class ValidationOutcome:
    matched: bool
    verdict: str
    confidence: int
    reason: str


def validate_candidate(
    product_name: str,
    source: SourceConfig,
    title: str,
    snippet: str,
    source_kind: str,
    score: float,
    product_context: str = '',
    extra_negative_hints: list[str] | None = None,
) -> ValidationOutcome:
    title = title or ''
    snippet = snippet or ''
    hay = compact_text(f'{title} {snippet}', 2000)

    if not hay:
        return ValidationOutcome(False, 'no_match', 0, 'empty page')

    merged_negative_hints = [*source.negative_hints, *(extra_negative_hints or [])]
    if contains_negative_page_signal(title, snippet, merged_negative_hints):
        return ValidationOutcome(False, 'no_match', 0, 'negative page signal')

    signals = analyze_text(product_name, title, snippet, product_context)
    one_word_query = signals.product_total <= 1
    strong_semantic = signals.synonym_hits >= 1 and signals.context_hits >= 2
    strong_identifier = signals.identifier_hits >= 1 and (signals.product_hits >= 1 or signals.synonym_hits >= 1)
    exact_or_near_exact = signals.exact_phrase or signals.product_hits >= max(1, signals.product_total - 1)

    if signals.negative_hits:
        generic_term_conflict = one_word_query and signals.context_hits == 0 and signals.identifier_hits == 0
        if generic_term_conflict or not (signals.exact_phrase or strong_identifier or strong_semantic):
            return ValidationOutcome(False, 'no_match', 0, 'context points to a different product domain')

    if source_kind.startswith('dataset:') and (exact_or_near_exact or strong_identifier or strong_semantic):
        confidence = 92 if signals.exact_phrase else 84
        return ValidationOutcome(True, 'match', confidence, 'dataset row matched product or model context')

    if is_generic_portal_page(title, snippet) and not (signals.exact_phrase or strong_identifier or strong_semantic):
        return ValidationOutcome(False, 'no_match', 0, 'generic portal page without product evidence')

    if source.category == 'company_registry' and not (signals.exact_phrase or strong_identifier):
        return ValidationOutcome(False, 'no_match', 0, 'company registry without explicit product evidence')

    if signals.exact_phrase or strong_identifier or strong_semantic:
        confidence = 88 if source_kind in {'source_search', 'search_template'} else 80
        reason = 'product phrase or context-specific model evidence present'
        return ValidationOutcome(True, 'match', confidence, reason)

    if one_word_query:
        if signals.product_hits >= 1 and signals.context_hits >= 1 and score >= 4.0:
            return ValidationOutcome(True, 'possible', 64, 'generic product term supported by context qualifiers')
        if signals.product_hits >= 1 and score >= 4.0 and source.category in {'tender_portal', 'marketplace', 'product_registry'}:
            return ValidationOutcome(True, 'possible', 60, 'single-word query found in focused source')
        return ValidationOutcome(False, 'no_match', 0, 'single-word query needs context, model, or stronger evidence')

    if signals.product_total and signals.product_hits >= max(2, signals.product_total - 1) and score >= 4.5:
        return ValidationOutcome(True, 'possible', 66, 'strong token overlap')

    return ValidationOutcome(False, 'no_match', 0, 'insufficient product evidence')


def infer_amount_kind(source_category: str, amount: str) -> str:
    if not amount:
        return 'registry_only' if source_category in {'product_registry', 'company_registry', 'open_data'} else 'none'
    if source_category in {'tender_portal', 'marketplace'}:
        return 'contract_amount'
    return 'price'

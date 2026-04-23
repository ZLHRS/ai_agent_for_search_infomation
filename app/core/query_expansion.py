from __future__ import annotations

from dataclasses import dataclass
import re


DOMAIN_GROUPS: dict[str, dict[str, set[str]]] = {
    'power_equipment': {
        'terms': {
            'generator', 'genset', 'gen-set', 'diesel', 'standby', 'backup', 'power', 'kva', 'kw',
            'alternator', 'powerstation', 'power-unit', 'дизель', 'генератор', 'дгу', 'электростанция',
        },
        'negative': {'software', 'license', 'subscription', 'saas', 'cloud', 'image', 'ai'},
    },
    'software': {
        'terms': {
            'software', 'license', 'subscription', 'saas', 'cloud', 'platform', 'application',
            'generator-app', 'generator-software', 'программное', 'по', 'лицензия',
        },
        'negative': {'diesel', 'genset', 'standby', 'kva', 'kw', 'generator', 'дгу', 'генератор'},
    },
}

SYNONYM_EQUIVALENTS: dict[str, set[str]] = {
    'generator': {'generator', 'genset', 'gen-set', 'power unit', 'power-unit', 'электростанция', 'дгу', 'генератор'},
    'genset': {'generator', 'genset', 'gen-set', 'power unit', 'power-unit', 'электростанция', 'дгу', 'генератор'},
    'software': {'software', 'application', 'platform', 'saas', 'subscription', 'программное обеспечение', 'по'},
}

STOPWORDS = {
    'for', 'the', 'and', 'with', 'from', 'that', 'this', 'into', 'your', 'you', 'our', 'per',
    'для', 'с', 'на', 'по', 'и', 'или', 'под', 'над', 'из', 'к', 'от', 'до',
}


@dataclass(slots=True)
class QuerySignals:
    product_name: str
    product_context: str
    product_tokens: list[str]
    context_tokens: list[str]
    positive_terms: set[str]
    negative_terms: set[str]
    synonym_groups: list[set[str]]
    identifier_tokens: set[str]
    search_queries: list[str]


@dataclass(slots=True)
class TextSignals:
    exact_phrase: bool
    product_hits: int
    product_total: int
    context_hits: int
    context_total: int
    synonym_hits: int
    identifier_hits: int
    negative_hits: int


TOKEN_RE = re.compile(r"[\w\-]+", flags=re.UNICODE)


def normalize_token(token: str) -> str:
    return token.lower().replace('ё', 'е').strip()


def canonical_token(token: str) -> str:
    return re.sub(r'[^a-zа-я0-9]+', '', normalize_token(token), flags=re.IGNORECASE)


def tokenize(text: str) -> list[str]:
    return [normalize_token(match.group(0)) for match in TOKEN_RE.finditer(text or '') if match.group(0).strip()]


def canonical_tokens(text: str) -> set[str]:
    values = {canonical_token(token) for token in tokenize(text)}
    return {value for value in values if value}


def _identifier_tokens(text: str) -> set[str]:
    found: set[str] = set()
    for token in tokenize(text):
        canonical = canonical_token(token)
        if not canonical:
            continue
        has_digit = any(ch.isdigit() for ch in canonical)
        has_alpha = any(ch.isalpha() for ch in canonical)
        if has_digit and (has_alpha or len(canonical) >= 4):
            found.add(canonical)
    return found


def _select_domain_terms(product_name: str, product_context: str) -> tuple[set[str], set[str], list[set[str]]]:
    combined_tokens = set(tokenize(f'{product_name} {product_context}'))
    positive: set[str] = set()
    negative: set[str] = set()
    groups: list[set[str]] = []

    for config in DOMAIN_GROUPS.values():
        if combined_tokens & config['terms']:
            positive.update(config['terms'])
            groups.append(set(config['terms']))

    for token in combined_tokens:
        if token in SYNONYM_EQUIVALENTS:
            group = set(SYNONYM_EQUIVALENTS[token])
            groups.append(group)
            positive.update(group)

    if positive:
        for config in DOMAIN_GROUPS.values():
            if positive & config['terms']:
                negative.update(config['negative'])

    deduped_groups: list[set[str]] = []
    seen: set[tuple[str, ...]] = set()
    for group in groups:
        key = tuple(sorted(group))
        if key in seen:
            continue
        seen.add(key)
        deduped_groups.append(group)

    return positive, negative, deduped_groups


def build_query_signals(product_name: str, product_context: str = '') -> QuerySignals:
    product_tokens = tokenize(product_name)
    context_tokens = [
        token for token in tokenize(product_context)
        if token not in product_tokens and token not in STOPWORDS
    ]
    positive_terms, negative_terms, synonym_groups = _select_domain_terms(product_name, product_context)
    identifier_tokens = _identifier_tokens(f'{product_name} {product_context}')

    search_queries: list[str] = []
    base_query = ' '.join(dict.fromkeys(product_tokens)).strip()
    if base_query:
        search_queries.append(base_query)

    if context_tokens:
        focused = ' '.join(dict.fromkeys((context_tokens[:4] + product_tokens[:3]))).strip()
        if focused and focused not in search_queries:
            search_queries.append(focused)

    if identifier_tokens:
        identifier_query = ' '.join(sorted(identifier_tokens))
        if identifier_query and identifier_query not in search_queries:
            search_queries.append(identifier_query)

    return QuerySignals(
        product_name=product_name,
        product_context=product_context,
        product_tokens=product_tokens,
        context_tokens=context_tokens,
        positive_terms=positive_terms,
        negative_terms=negative_terms,
        synonym_groups=synonym_groups,
        identifier_tokens=identifier_tokens,
        search_queries=search_queries,
    )


def analyze_text(product_name: str, title: str, snippet: str, product_context: str = '') -> TextSignals:
    hay = f'{title} {snippet}'.lower()
    hay_tokens = set(tokenize(hay))
    hay_canonical = canonical_tokens(hay)
    signals = build_query_signals(product_name, product_context)

    exact_phrase = normalize_token(product_name) in hay
    product_hits = sum(1 for token in signals.product_tokens if token in hay_tokens or canonical_token(token) in hay_canonical)
    context_hits = sum(1 for token in signals.context_tokens if token in hay_tokens or canonical_token(token) in hay_canonical)
    synonym_hits = 0
    for group in signals.synonym_groups:
        if any(normalize_token(term) in hay or canonical_token(term) in hay_canonical for term in group):
            synonym_hits += 1
    identifier_hits = sum(1 for token in signals.identifier_tokens if token in hay_canonical)
    negative_hits = sum(1 for token in signals.negative_terms if normalize_token(token) in hay)

    return TextSignals(
        exact_phrase=exact_phrase,
        product_hits=product_hits,
        product_total=len(signals.product_tokens),
        context_hits=context_hits,
        context_total=len(signals.context_tokens),
        synonym_hits=synonym_hits,
        identifier_hits=identifier_hits,
        negative_hits=negative_hits,
    )

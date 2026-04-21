from __future__ import annotations

import html
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

GENERIC_NEGATIVE_TERMS = {
    'just a moment', 'announcement not found', 'unavailable', 'registration', 'register',
    'login', 'log in', 'sign in', 'welcome', 'cookies', 'access denied', 'forbidden',
    'robot check', 'captcha', 'подождите', 'войти', 'регистрация'
}

GENERIC_PORTAL_TERMS = {
    'open solicitations', 'public procurement', 'реестр', 'registry', 'каталог', 'platform',
    'государственные закупки', 'государственная информационная система', 'портал', 'datasets'
}

CURRENCY_PATTERNS = [
    r'(?:€|EUR)\s?[\d\s.,]{2,}',
    r'(?:\$|USD)\s?[\d\s.,]{2,}',
    r'(?:₽|RUB|руб\.?|рублей)\s?[\d\s.,]{2,}',
    r'(?:₸|KZT|тенге)\s?[\d\s.,]{2,}',
    r'(?:PLN|zł)\s?[\d\s.,]{2,}',
    r'(?:UAH|грн\.?|₴)\s?[\d\s.,]{2,}',
    r'(?:CNY|¥)\s?[\d\s.,]{2,}',
]


def normalize_ws(text: str) -> str:
    text = html.unescape(text or '')
    return re.sub(r'\s+', ' ', text).strip()


def html_to_text(content: str) -> tuple[str, str]:
    soup = BeautifulSoup(content, 'html.parser')
    title = normalize_ws(soup.title.get_text(' ')) if soup.title else ''
    for tag in soup(['script', 'style', 'noscript']):
        tag.decompose()
    body_text = normalize_ws(soup.get_text(' ', strip=True))
    return title, body_text


def domain_from_url(url: str) -> str:
    return urlparse(url).netloc.lower()


def query_terms(product_name: str) -> list[str]:
    raw_tokens = [t.strip().lower() for t in re.split(r"[^\w\-]+", product_name, flags=re.UNICODE) if t.strip()]
    whole = product_name.lower().strip()
    tokens = [t for t in raw_tokens if len(t) >= 2]
    return list(dict.fromkeys(([whole] if whole else []) + tokens))


def exact_phrase_present(product_name: str, text: str, title: str = '') -> bool:
    hay = f'{title} {text}'.lower()
    return product_name.lower().strip() in hay


def token_overlap(product_name: str, text: str, title: str = '') -> tuple[int, int]:
    hay = f'{title} {text}'.lower()
    tokens = [t for t in query_terms(product_name) if ' ' not in t]
    if not tokens:
        return 0, 0
    hits = sum(1 for t in tokens if t in hay)
    return hits, len(tokens)


def text_score(product_name: str, text: str, title: str = '') -> float:
    hay = f'{title} {text}'.lower()
    score = 0.0
    for term in query_terms(product_name):
        if term and term in hay:
            score += 1.0 if len(term) <= 4 else 2.0
    if exact_phrase_present(product_name, text, title):
        score += 5.0
    hits, total = token_overlap(product_name, text, title)
    if total:
        score += hits / total
    return score


def snippet_around_match(product_name: str, text: str, size: int = 500) -> str:
    hay = text.lower()
    needle = product_name.lower()
    idx = hay.find(needle)
    if idx == -1:
        return text[:size]
    start = max(0, idx - size // 2)
    end = min(len(text), idx + size // 2)
    return text[start:end]


def contains_negative_page_signal(title: str, text: str, extra_terms: list[str] | None = None) -> bool:
    hay = f'{title} {text}'.lower()
    terms = set(GENERIC_NEGATIVE_TERMS)
    if extra_terms:
        terms.update(t.lower() for t in extra_terms)
    return any(term in hay for term in terms)


def is_generic_portal_page(title: str, text: str) -> bool:
    hay = f'{title} {text[:1500]}'.lower()
    return sum(1 for term in GENERIC_PORTAL_TERMS if term in hay) >= 2


def extract_amount(text: str) -> tuple[str, str]:
    for pattern in CURRENCY_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            amount = normalize_ws(match.group(0))
            upper = amount.upper()
            if 'EUR' in upper or '€' in amount:
                return amount, 'EUR'
            if 'USD' in upper or '$' in amount:
                return amount, 'USD'
            if 'RUB' in upper or 'РУБ' in upper or '₽' in amount:
                return amount, 'RUB'
            if 'KZT' in upper or '₸' in amount or 'ТЕНГЕ' in upper:
                return amount, 'KZT'
            if 'PLN' in upper or 'ZŁ' in upper:
                return amount, 'PLN'
            if 'UAH' in upper or '₴' in amount or 'ГРН' in upper:
                return amount, 'UAH'
            if 'CNY' in upper or '¥' in amount:
                return amount, 'CNY'
            return amount, ''
    return '', ''


def compact_text(text: str, max_chars: int = 1200) -> str:
    return normalize_ws(text)[:max_chars]

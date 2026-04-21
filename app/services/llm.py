from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.config import settings
from app.models import FactBlock
from app.services.matchers import infer_amount_kind
from app.services.text_tools import extract_amount


class OllamaClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=settings.request_timeout_seconds)

    async def close(self) -> None:
        await self._client.aclose()

    async def health(self) -> dict[str, Any]:
        try:
            response = await self._client.get(f'{settings.ollama_base_url}/api/tags')
            response.raise_for_status()
            data = response.json()
            models = [m.get('name', '') for m in data.get('models', [])]
            return {'available': settings.ollama_model in models, 'models': models}
        except Exception as exc:
            return {'available': False, 'error': str(exc)}

    async def summarize_match(
        self,
        product_name: str,
        source_name: str,
        source_category: str,
        url: str,
        title: str,
        text: str,
    ) -> dict[str, Any]:
        prompt = f"""
Ты получаешь уже ПОДТВЕРЖДЁННОЕ совпадение по товару.
Нельзя спорить с matched: товар уже найден.
Твоя задача — кратко пересказать, что именно найдено, и вытащить поля.
Ответь СТРОГО JSON.

product_name: {product_name}
source_name: {source_name}
source_category: {source_category}
url: {url}
page_title: {title}
text:
{text[:settings.llm_snippet_chars]}

Верни JSON вида:
{{
  "short_info": "...",
  "facts": {{
    "brand": "",
    "availability": "",
    "supplier": "",
    "buyer": "",
    "registry_number": "",
    "product_type": "",
    "key_specs": ["..."]
  }}
}}

Не выдумывай цены и суммы. Если поля нет — оставь пустым.
""".strip()
        response = await self._client.post(
            f'{settings.ollama_base_url}/api/generate',
            json={
                'model': settings.ollama_model,
                'prompt': prompt,
                'stream': False,
                'format': 'json',
            },
        )
        response.raise_for_status()
        data = response.json()
        raw = data.get('response', '{}')
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            raise


def heuristic_details(product_name: str, source_category: str, title: str, text: str) -> dict[str, Any]:
    amount, currency = extract_amount(f'{title} {text}')
    facts = FactBlock(
        amount=amount,
        amount_kind=infer_amount_kind(source_category, amount),
        currency=currency,
        key_specs=[],
    ).model_dump()
    short_info = 'Найдена релевантная запись по товару.' if product_name.lower() in f'{title} {text}'.lower() else 'Найден вероятно релевантный фрагмент.'
    return {'short_info': short_info, 'facts': facts}

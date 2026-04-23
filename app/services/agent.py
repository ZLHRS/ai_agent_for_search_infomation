from __future__ import annotations

from urllib.parse import quote_plus

from app.config import settings
from app.core.source_router import get_source_adapter
from app.models import AnalysisResponse, CandidateEvidence, FactBlock, SourceResult
from app.services.dataset_tools import search_dataset
from app.services.fetchers import HttpFetcher, browser_get_text_page, gather_limited
from app.services.llm import OllamaClient, heuristic_details
from app.services.matchers import infer_amount_kind, validate_candidate
from app.services.source_registry import SourceConfig, SourceRegistry
from app.services.text_tools import extract_amount, snippet_around_match, text_score


class ProductSearchAgent:
    def __init__(self, registry: SourceRegistry) -> None:
        self.registry = registry
        self.fetcher = HttpFetcher()
        self.llm = OllamaClient()

    async def close(self) -> None:
        await self.fetcher.close()
        await self.llm.close()

    async def analyze(
        self,
        product_name: str,
        max_results_per_source: int,
        include_disabled: bool,
        product_context: str = '',
    ) -> AnalysisResponse:
        sources = self.registry.list_sources(include_disabled=include_disabled)
        coros = [
            self._analyze_source(src, product_name, max_results_per_source, product_context)
            for src in sources
        ]
        raw_results = await gather_limited(coros, settings.max_concurrency)
        results: list[SourceResult] = []
        for item, src in zip(raw_results, sources):
            if isinstance(item, Exception):
                results.append(SourceResult(
                    source_name=src.name,
                    source_category=src.category,
                    base_url=src.base_url,
                    modes_used=src.modes,
                    error=str(item),
                ))
            else:
                results.append(item)

        matched = [r for r in results if r.matched]
        possible = [r for r in results if not r.matched and r.verdict == 'possible']
        if matched:
            summary = f'По товару "{product_name}" найдены подтверждённые совпадения в {len(matched)} источниках.'
        elif possible:
            summary = f'По товару "{product_name}" есть только вероятные совпадения, подтверждённых записей нет.'
        else:
            summary = f'По товару "{product_name}" подтверждённых совпадений в доступных источниках не найдено.'
        return AnalysisResponse(product_name=product_name, results=results, final_summary=summary)

    async def _analyze_source(
        self,
        src: SourceConfig,
        product_name: str,
        max_results: int,
        product_context: str,
    ) -> SourceResult:
        adapter = get_source_adapter(src)
        plan = adapter.build_search_plan(product_name, product_context)
        evidences: list[CandidateEvidence] = []
        used_urls: list[str] = []
        errors: list[str] = []

        async def push_page(source_kind: str, url: str, title: str, text: str, score_boost: float = 0.0):
            score = text_score(f'{product_name} {product_context}'.strip(), text, title) + score_boost
            ev = CandidateEvidence(
                url=url,
                title=title,
                snippet=snippet_around_match(product_name, text),
                source_kind=source_kind,
                score=score,
                exact_match=product_name.lower() in f'{title} {text}'.lower(),
                relevance_reason='',
            )
            evidences.append(ev)
            used_urls.append(url)

        for request in plan.requests:
            try:
                if request.kind == 'dataset':
                    hits = await search_dataset(self.fetcher, request.url, product_name)
                    for hit in hits[:max_results]:
                        evidences.append(CandidateEvidence(**hit))
                        used_urls.append(hit['url'])
                    continue

                if request.kind == 'domain_search':
                    candidate_urls = await self.fetcher.duckduckgo_site_search(src.domain, request.url, settings.max_candidate_urls_per_source)
                    for candidate_url in candidate_urls:
                        try:
                            page = await self.fetcher.get_text_page(candidate_url)
                            await push_page('domain_search', page.url, page.title, page.text, request.score_boost)
                        except Exception:
                            continue
                    continue

                if request.fetch_mode == 'browser' or request.kind == 'browser':
                    page = await browser_get_text_page(request.url)
                else:
                    page = await self.fetcher.get_text_page(request.url)
                await push_page(request.kind, page.url, page.title, page.text, request.score_boost)
            except Exception as exc:
                errors.append(f'{request.kind}: {exc}')

        dedup: dict[tuple[str, str], CandidateEvidence] = {}
        for ev in evidences:
            key = (ev.url, ev.source_kind)
            if key not in dedup or ev.score > dedup[key].score:
                dedup[key] = ev
        ranked = sorted(dedup.values(), key=lambda x: x.score, reverse=True)[:max_results]

        validated: list[tuple[CandidateEvidence, object]] = []
        for ev in ranked:
            outcome = validate_candidate(
                product_name=product_name,
                product_context=product_context,
                source=src,
                title=ev.title,
                snippet=ev.snippet,
                source_kind=ev.source_kind,
                score=ev.score,
                extra_negative_hints=adapter.negative_signals,
            )
            ev.relevance_reason = outcome.reason
            if outcome.matched or outcome.verdict == 'possible':
                validated.append((ev, outcome))

        if not validated:
            return SourceResult(
                source_name=src.name,
                source_category=src.category,
                base_url=src.base_url,
                modes_used=src.modes,
                used_urls=list(dict.fromkeys(used_urls)),
                matched=False,
                verdict='no_match',
                short_info='Подтверждённой записи по товару в этом источнике не найдено.',
                confidence=0,
                llm_mode='heuristic',
                evidences=ranked,
                error='; '.join(errors) if errors else None,
            )

        best, outcome = sorted(
            validated,
            key=lambda pair: (pair[1].matched, pair[1].confidence, pair[0].score),
            reverse=True,
        )[0]
        amount, currency = extract_amount(f'{best.title} {best.snippet}')
        extracted = adapter.extract_facts(best.url, best.title, best.snippet)
        llm_health = await self.llm.health()
        llm_available = bool(llm_health.get('available'))
        facts = FactBlock(
            amount=amount,
            amount_kind=infer_amount_kind(src.category, amount),
            currency=currency,
            brand=extracted.get('brand', ''),
            supplier=extracted.get('supplier', ''),
            buyer=extracted.get('buyer', ''),
            registry_number=extracted.get('registry_number', ''),
            product_type=extracted.get('product_type', ''),
        )
        short_info = 'Найдена подтверждённая запись по товару.' if outcome.matched else 'Найдено вероятное совпадение по товару.'
        llm_mode = 'heuristic'

        if llm_available:
            try:
                payload = await self.llm.summarize_match(product_name, src.name, src.category, best.url, best.title, best.snippet)
                facts_data = payload.get('facts') or {}
                facts = FactBlock(
                    amount=amount,
                    amount_kind=infer_amount_kind(src.category, amount),
                    currency=currency,
                    brand=facts.brand or facts_data.get('brand', ''),
                    availability=facts_data.get('availability', ''),
                    supplier=facts.supplier or facts_data.get('supplier', ''),
                    buyer=facts.buyer or facts_data.get('buyer', ''),
                    registry_number=facts.registry_number or facts_data.get('registry_number', ''),
                    product_type=facts.product_type or facts_data.get('product_type', ''),
                    key_specs=facts_data.get('key_specs') or [],
                )
                short_info = payload.get('short_info', short_info) or short_info
                llm_mode = 'ollama'
            except Exception as exc:
                errors.append(f'ollama: {exc}')
                heur = heuristic_details(product_name, src.category, best.title, best.snippet)
                short_info = heur['short_info']
        else:
            heur = heuristic_details(product_name, src.category, best.title, best.snippet)
            short_info = heur['short_info']

        return SourceResult(
            source_name=src.name,
            source_category=src.category,
            base_url=src.base_url,
            modes_used=src.modes,
            used_urls=list(dict.fromkeys(used_urls)),
            matched=bool(outcome.matched),
            verdict=outcome.verdict,
            short_info=short_info,
            facts=facts,
            confidence=int(outcome.confidence),
            llm_mode=llm_mode,
            evidences=ranked,
            error='; '.join(errors) if errors else None,
        )

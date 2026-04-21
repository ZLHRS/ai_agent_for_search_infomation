from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin
from xml.etree import ElementTree as ET

import pandas as pd
from bs4 import BeautifulSoup

from app.config import settings
from app.services.fetchers import HttpFetcher
from app.services.text_tools import normalize_ws, snippet_around_match, text_score, exact_phrase_present, token_overlap


async def discover_dataset_links(fetcher: HttpFetcher, landing_url: str) -> list[str]:
    raw_bytes, _, final_url = await fetcher.get_bytes(landing_url)
    html = raw_bytes.decode(errors='ignore')
    soup = BeautifulSoup(html, 'html.parser')
    links: list[str] = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        low = href.lower()
        if any(ext in low for ext in ('.xlsx', '.xls', '.csv', '.json', '.xml', '.zip', 'export')):
            links.append(urljoin(final_url, href))
    return list(dict.fromkeys(links))


def _flatten_rows(rows: Iterable[Iterable[object]]) -> list[str]:
    texts: list[str] = []
    for row in rows:
        line = normalize_ws(' | '.join('' if v is None else str(v) for v in row))
        if line:
            texts.append(line)
    return texts


def _row_hit(product_name: str, line: str, source_url: str, source_kind: str) -> dict | None:
    score = text_score(product_name, line)
    exact = exact_phrase_present(product_name, line)
    hits, total = token_overlap(product_name, line)
    if not exact and (total == 0 or hits == 0):
        return None
    if len(product_name.split()) == 1 and not exact and hits < 1:
        return None
    return {
        'url': source_url,
        'title': '',
        'snippet': snippet_around_match(product_name, line, 450),
        'source_kind': source_kind,
        'score': score + (1.0 if exact else 0.0),
        'exact_match': exact,
        'relevance_reason': 'dataset row contains product tokens' if not exact else 'dataset row contains exact product phrase',
    }


def _parse_xlsx_bytes(content: bytes) -> list[str]:
    frames = pd.read_excel(io.BytesIO(content), sheet_name=None, dtype=str)
    lines: list[str] = []
    for frame in frames.values():
        lines.extend(_flatten_rows(frame.fillna('').itertuples(index=False, name=None)))
    return lines


def _parse_csv_bytes(content: bytes) -> list[str]:
    text = content.decode(errors='ignore')
    reader = csv.reader(io.StringIO(text))
    return _flatten_rows(reader)


def _parse_json_bytes(content: bytes) -> list[str]:
    obj = json.loads(content.decode(errors='ignore'))
    lines: list[str] = []

    def walk(value):
        if isinstance(value, dict):
            line = normalize_ws(' | '.join(f'{k}: {v}' for k, v in value.items() if not isinstance(v, (dict, list))))
            if line:
                lines.append(line)
            for v in value.values():
                walk(v)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(obj)
    return lines


def _parse_xml_bytes(content: bytes) -> list[str]:
    root = ET.fromstring(content)
    lines: list[str] = []
    for elem in root.iter():
        texts = [normalize_ws(t) for t in elem.itertext()]
        line = normalize_ws(' | '.join(t for t in texts if t))
        if line:
            lines.append(line)
    return lines


def _parse_zip_bytes(content: bytes) -> list[tuple[str, list[str]]]:
    found: list[tuple[str, list[str]]] = []
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        for info in zf.infolist()[:20]:
            name = info.filename.lower()
            with zf.open(info) as fp:
                data = fp.read()
            if name.endswith(('.xlsx', '.xls')):
                found.append((info.filename, _parse_xlsx_bytes(data)))
            elif name.endswith('.csv'):
                found.append((info.filename, _parse_csv_bytes(data)))
            elif name.endswith('.json'):
                found.append((info.filename, _parse_json_bytes(data)))
            elif name.endswith('.xml'):
                try:
                    found.append((info.filename, _parse_xml_bytes(data)))
                except ET.ParseError:
                    continue
    return found


async def search_dataset(fetcher: HttpFetcher, landing_url: str, product_name: str) -> list[dict]:
    dataset_links = await discover_dataset_links(fetcher, landing_url)
    results: list[dict] = []
    for link in dataset_links[:4]:
        try:
            content, _, final_url = await fetcher.get_bytes(link)
        except Exception:
            continue
        ext = Path(final_url.split('?')[0]).suffix.lower()
        try:
            if ext in {'.xlsx', '.xls'}:
                lines = _parse_xlsx_bytes(content)
                for line in lines:
                    hit = _row_hit(product_name, line, final_url, 'dataset:xlsx')
                    if hit:
                        results.append(hit)
            elif ext == '.csv':
                lines = _parse_csv_bytes(content)
                for line in lines:
                    hit = _row_hit(product_name, line, final_url, 'dataset:csv')
                    if hit:
                        results.append(hit)
            elif ext == '.json':
                lines = _parse_json_bytes(content)
                for line in lines:
                    hit = _row_hit(product_name, line, final_url, 'dataset:json')
                    if hit:
                        results.append(hit)
            elif ext == '.xml':
                lines = _parse_xml_bytes(content)
                for line in lines:
                    hit = _row_hit(product_name, line, final_url, 'dataset:xml')
                    if hit:
                        results.append(hit)
            elif ext == '.zip':
                for member_name, lines in _parse_zip_bytes(content):
                    for line in lines:
                        hit = _row_hit(product_name, line, f'{final_url}#{member_name}', 'dataset:zip')
                        if hit:
                            results.append(hit)
        except Exception:
            continue
    results.sort(key=lambda x: x['score'], reverse=True)
    return results[: settings.max_dataset_hits]

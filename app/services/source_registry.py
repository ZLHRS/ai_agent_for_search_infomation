from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class SourceConfig:
    name: str
    category: str
    base_url: str
    domain: str
    enabled: bool
    modes: list[str]
    search_url_template: str | None = None
    notes: str | None = None
    negative_hints: list[str] = field(default_factory=list)


class SourceRegistry:
    def __init__(self, path: str | Path):
        self._path = Path(path)
        raw = json.loads(self._path.read_text(encoding='utf-8'))
        self._sources = [SourceConfig(**item) for item in raw]

    def list_sources(self, include_disabled: bool = False) -> list[SourceConfig]:
        if include_disabled:
            return list(self._sources)
        return [s for s in self._sources if s.enabled]

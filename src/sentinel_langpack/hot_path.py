from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from sentinel_langpack.wave1 import (
    PackLexicon,
    PackLexiconEntry,
    PackNormalization,
    Wave1PackManifest,
    load_wave1_registry,
    wave1_packs_in_priority_order,
)

WORD_BOUNDARY_CHARS = r"[0-9A-Za-zÀ-ÖØ-öø-ÿ']"
TERM_TOKEN_PATTERN = re.compile(r"[0-9A-Za-zÀ-ÖØ-öø-ÿ']+")
DEFAULT_REGISTRY_PATH = Path("data/langpacks/registry.json")


def _resolve_registry_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return (Path.cwd() / candidate).resolve()


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_pack_root(registry_path: Path, manifest: Wave1PackManifest) -> Path:
    root = registry_path.parent
    pack_dir = Path(manifest.directory)
    if pack_dir.is_absolute():
        return pack_dir.resolve()
    return (root / pack_dir).resolve()


def _normalize_text(text: str, replacements: dict[str, str]) -> str:
    normalized = unicodedata.normalize("NFKC", text).replace("’", "'").lower()
    for source, target in replacements.items():
        source_key = source.strip().lower()
        if not source_key:
            continue
        normalized = normalized.replace(source_key, target.strip().lower())
    return normalized


def _compile_term_pattern(term: str) -> re.Pattern[str]:
    normalized = unicodedata.normalize("NFKC", term).replace("’", "'").lower().strip()
    if not normalized:
        return re.compile(r"(?!x)x")
    tokens = TERM_TOKEN_PATTERN.findall(normalized)
    if not tokens:
        return re.compile(re.escape(normalized))
    boundary_start = rf"(?<!{WORD_BOUNDARY_CHARS})"
    boundary_end = rf"(?!{WORD_BOUNDARY_CHARS})"
    token_pattern = r"[\W_]+".join(re.escape(token) for token in tokens)
    return re.compile(rf"{boundary_start}{token_pattern}{boundary_end}")


@dataclass(frozen=True)
class PackMatcher:
    language: str
    pack_version: str
    compiled_entries: list[tuple[PackLexiconEntry, re.Pattern[str]]]
    normalization: dict[str, str]

    def match(self, text: str) -> list[PackLexiconEntry]:
        normalized = _normalize_text(text, self.normalization)
        matches: list[PackLexiconEntry] = []
        for entry, pattern in self.compiled_entries:
            if pattern.search(normalized):
                matches.append(entry)
        return matches


def _build_matcher(
    manifest: Wave1PackManifest,
    *,
    registry_path: Path,
) -> PackMatcher:
    pack_root = _resolve_pack_root(registry_path, manifest)
    normalization_payload = _load_json(pack_root / manifest.artifacts.normalization)
    lexicon_payload = _load_json(pack_root / manifest.artifacts.lexicon)
    normalization = PackNormalization.model_validate(normalization_payload)
    lexicon = PackLexicon.model_validate(lexicon_payload)
    compiled_entries = [(entry, _compile_term_pattern(entry.term)) for entry in lexicon.entries]
    return PackMatcher(
        language=manifest.language.strip().lower(),
        pack_version=manifest.pack_version,
        compiled_entries=compiled_entries,
        normalization=dict(normalization.replacements),
    )


@lru_cache(maxsize=1)
def get_wave1_pack_matchers() -> list[PackMatcher]:
    """Return compiled matchers for wave1 packs.

    Falls back to `[]` on missing or invalid registry/pack artifacts so the
    request path never fails due to optional pack data.
    """
    registry_path = _resolve_registry_path(DEFAULT_REGISTRY_PATH)
    try:
        registry = load_wave1_registry(registry_path)
        manifests = wave1_packs_in_priority_order(registry)
        return [_build_matcher(manifest, registry_path=registry_path) for manifest in manifests]
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError):
        return []

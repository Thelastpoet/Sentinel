from __future__ import annotations

from typing import Mapping


def resolve_pack_versions(pack_versions: Mapping[str, str]) -> dict[str, str]:
    """Return a normalized copy of configured pack versions.

    This keeps policy/runtime ownership separated from langpack concerns and
    provides a stable boundary for future pack registries.
    """
    normalized: dict[str, str] = {}
    for key, value in pack_versions.items():
        lang = str(key).strip()
        version = str(value).strip()
        if not lang or not version:
            continue
        normalized[lang] = version
    return normalized


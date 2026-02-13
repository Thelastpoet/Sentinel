from __future__ import annotations

from sentinel_langpack.registry import resolve_pack_versions


def test_resolve_pack_versions_normalizes_and_filters_empty_values() -> None:
    resolved = resolve_pack_versions(
        {
            " en ": " pack-en-1.0 ",
            "sw": "pack-sw-1.0",
            "": "pack-unknown",
            "sh": "",
        }
    )
    assert resolved == {"en": "pack-en-1.0", "sw": "pack-sw-1.0"}


def test_resolve_pack_versions_returns_copy() -> None:
    source = {"en": "pack-en-0.1"}
    resolved = resolve_pack_versions(source)
    assert resolved == {"en": "pack-en-0.1"}
    assert resolved is not source

from __future__ import annotations

import importlib


def test_lexicon_shim_aliases_new_package_module() -> None:
    old = importlib.import_module("sentinel_api.lexicon")
    new = importlib.import_module("sentinel_lexicon.lexicon")
    assert old is new


def test_lexicon_repository_shim_aliases_new_package_module() -> None:
    old = importlib.import_module("sentinel_api.lexicon_repository")
    new = importlib.import_module("sentinel_lexicon.lexicon_repository")
    assert old is new


def test_router_language_shim_aliases_new_package_module() -> None:
    old = importlib.import_module("sentinel_api.language_router")
    new = importlib.import_module("sentinel_router.language_router")
    assert old is new


def test_langpack_shim_aliases_new_package_module() -> None:
    old = importlib.import_module("sentinel_api.langpack")
    new = importlib.import_module("sentinel_langpack.registry")
    assert old is new

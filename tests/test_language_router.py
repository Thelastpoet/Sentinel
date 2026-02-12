from __future__ import annotations

import logging

import sentinel_api.language_router as language_router
from sentinel_api.language_router import detect_language_spans
from sentinel_api.policy_config import get_policy_config, reset_policy_config_cache


def setup_function() -> None:
    reset_policy_config_cache()


def teardown_function() -> None:
    reset_policy_config_cache()
    language_router.reset_language_router_cache()


def test_detect_language_spans_defaults_to_single_en_span_for_plain_english() -> None:
    config = get_policy_config()
    text = "We should discuss policy peacefully."
    spans = detect_language_spans(
        text,
        sw_hints=config.language_hints.sw,
        sh_hints=config.language_hints.sh,
        fallback_lang="en",
    )
    assert len(spans) == 1
    assert spans[0].lang == "en"
    assert spans[0].start == 0
    assert spans[0].end == len(text)


def test_detect_language_spans_returns_multiple_spans_for_code_switch() -> None:
    config = get_policy_config()
    text = "manze we should discuss sasa peacefully."
    spans = detect_language_spans(
        text,
        sw_hints=config.language_hints.sw,
        sh_hints=config.language_hints.sh,
        fallback_lang="en",
    )
    langs = [span.lang for span in spans]
    assert len(spans) >= 3
    assert "sh" in langs
    assert "sw" in langs
    assert "en" in langs
    assert spans[0].start == 0
    assert spans[-1].end == len(text)


def test_detect_language_spans_empty_text_returns_zero_width_fallback_span() -> None:
    config = get_policy_config()
    spans = detect_language_spans(
        "",
        sw_hints=config.language_hints.sw,
        sh_hints=config.language_hints.sh,
        fallback_lang="en",
    )
    assert len(spans) == 1
    assert spans[0].lang == "en"
    assert spans[0].start == 0
    assert spans[0].end == 0


def test_load_fasttext_model_logs_debug_when_module_missing(monkeypatch, caplog) -> None:
    caplog.set_level(logging.DEBUG, logger="sentinel_router.language_router")
    language_router.reset_language_router_cache()
    monkeypatch.setenv("SENTINEL_LID_MODEL_PATH", __file__)

    def _raise_module_not_found(_name: str):
        raise ModuleNotFoundError("fasttext not installed")

    monkeypatch.setattr(language_router.importlib, "import_module", _raise_module_not_found)
    assert language_router._load_fasttext_model() is None
    assert "fastText module unavailable for LID routing" in caplog.text

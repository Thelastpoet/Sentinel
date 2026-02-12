from __future__ import annotations

from sentinel_api.language_router import detect_language_spans
from sentinel_api.policy_config import get_policy_config, reset_policy_config_cache


def setup_function() -> None:
    reset_policy_config_cache()


def teardown_function() -> None:
    reset_policy_config_cache()


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

from __future__ import annotations

import importlib
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from sentinel_api.models import LanguageSpan


TOKEN_PATTERN = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ']+")
DEFAULT_LID_CONFIDENCE_THRESHOLD = 0.80
SUPPORTED_LANGS = {"en", "sw", "sh"}


@dataclass(frozen=True)
class _TokenSpan:
    start: int
    end: int
    text: str


@lru_cache(maxsize=1)
def _load_fasttext_model():
    model_path = os.getenv("SENTINEL_LID_MODEL_PATH")
    if not model_path:
        return None
    path = Path(model_path)
    if not path.exists():
        return None
    try:
        fasttext = importlib.import_module("fasttext")
    except ModuleNotFoundError:
        return None
    try:
        return fasttext.load_model(str(path))
    except Exception:
        return None


def reset_language_router_cache() -> None:
    _load_fasttext_model.cache_clear()


def _tokenize(text: str) -> list[_TokenSpan]:
    return [
        _TokenSpan(start=match.start(), end=match.end(), text=match.group(0))
        for match in TOKEN_PATTERN.finditer(text)
    ]


def _confidence_threshold() -> float:
    raw = os.getenv("SENTINEL_LID_CONFIDENCE_THRESHOLD")
    if raw is None:
        return DEFAULT_LID_CONFIDENCE_THRESHOLD
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_LID_CONFIDENCE_THRESHOLD
    if value < 0 or value > 1:
        return DEFAULT_LID_CONFIDENCE_THRESHOLD
    return value


def _predict_with_model(token: str, fallback_lang: str) -> tuple[str, float] | None:
    model = _load_fasttext_model()
    if model is None:
        return None
    try:
        labels, scores = model.predict(token, k=1)
    except Exception:
        return None
    if not labels or not scores:
        return None
    label = str(labels[0]).replace("__label__", "").strip().lower()
    score = float(scores[0])
    if label not in SUPPORTED_LANGS:
        return fallback_lang, 0.0
    return label, score


def _classify_token_language(
    token_text: str,
    *,
    sw_hints: set[str],
    sh_hints: set[str],
    fallback_lang: str,
) -> str:
    normalized = token_text.lower()
    if normalized in sh_hints:
        return "sh"
    if normalized in sw_hints:
        return "sw"

    prediction = _predict_with_model(normalized, fallback_lang)
    if prediction is None:
        return fallback_lang
    predicted_lang, confidence = prediction
    if confidence >= _confidence_threshold():
        return predicted_lang
    return fallback_lang


def detect_language_spans(
    text: str,
    *,
    sw_hints: Iterable[str],
    sh_hints: Iterable[str],
    fallback_lang: str = "en",
) -> list[LanguageSpan]:
    if not text:
        return [LanguageSpan(start=0, end=0, lang=fallback_lang)]

    tokens = _tokenize(text)
    if not tokens:
        return [LanguageSpan(start=0, end=len(text), lang=fallback_lang)]

    normalized_sw_hints = {item.strip().lower() for item in sw_hints if item.strip()}
    normalized_sh_hints = {item.strip().lower() for item in sh_hints if item.strip()}

    char_langs: list[str | None] = [None] * len(text)

    for token in tokens:
        token_lang = _classify_token_language(
            token.text,
            sw_hints=normalized_sw_hints,
            sh_hints=normalized_sh_hints,
            fallback_lang=fallback_lang,
        )
        for index in range(token.start, token.end):
            char_langs[index] = token_lang

    first_assigned_index: int | None = next(
        (idx for idx, lang in enumerate(char_langs) if lang is not None),
        None,
    )
    if first_assigned_index is None:
        return [LanguageSpan(start=0, end=len(text), lang=fallback_lang)]

    first_lang = char_langs[first_assigned_index]
    assert first_lang is not None
    for idx in range(0, first_assigned_index):
        char_langs[idx] = first_lang

    active_lang = first_lang
    for idx in range(first_assigned_index, len(char_langs)):
        current = char_langs[idx]
        if current is None:
            char_langs[idx] = active_lang
            continue
        active_lang = current

    spans: list[LanguageSpan] = []
    span_start = 0
    current_lang = char_langs[0]
    assert current_lang is not None

    for idx in range(1, len(char_langs)):
        lang = char_langs[idx]
        assert lang is not None
        if lang == current_lang:
            continue
        spans.append(LanguageSpan(start=span_start, end=idx, lang=current_lang))
        span_start = idx
        current_lang = lang

    spans.append(LanguageSpan(start=span_start, end=len(char_langs), lang=current_lang))
    return spans

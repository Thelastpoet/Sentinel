from __future__ import annotations

import json

import pytest

from sentinel_core.eval_harness import EvalSample, evaluate_samples, load_eval_samples


class _Decision:
    def __init__(self, *, action: str, labels: list[str]) -> None:
        self.action = action
        self.labels = labels


def test_load_eval_samples_parses_jsonl_and_defaults_benign_flag(tmp_path) -> None:
    path = tmp_path / "eval.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "id": "s-1",
                        "text": "peaceful political debate",
                        "language": "en",
                        "labels": ["BENIGN_POLITICAL_SPEECH"],
                    }
                ),
                json.dumps(
                    {
                        "id": "s-2",
                        "text": "They should kill them now",
                        "language": "en",
                        "labels": ["INCITEMENT_VIOLENCE"],
                        "is_benign_political": False,
                        "is_code_switched": True,
                        "subgroup": "group-a",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    samples = load_eval_samples(path)
    assert len(samples) == 2
    assert samples[0].is_benign_political is True
    assert samples[0].is_code_switched is False
    assert samples[1].is_benign_political is False
    assert samples[1].is_code_switched is True
    assert samples[1].subgroup == "group-a"


def test_load_eval_samples_rejects_unknown_label(tmp_path) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_text(
        json.dumps(
            {
                "id": "s-1",
                "text": "sample",
                "language": "en",
                "labels": ["NOT_A_REAL_LABEL"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unknown label"):
        load_eval_samples(path)


def test_evaluate_samples_reports_language_metrics_and_benign_disparity() -> None:
    samples = [
        EvalSample(
            sample_id="s1",
            text="harmful en",
            language="en",
            labels=["INCITEMENT_VIOLENCE"],
            is_benign_political=False,
            subgroup=None,
        ),
        EvalSample(
            sample_id="s2",
            text="harmful sw",
            language="sw",
            labels=["ETHNIC_CONTEMPT"],
            is_benign_political=False,
            subgroup=None,
        ),
        EvalSample(
            sample_id="s3",
            text="benign a",
            language="en",
            labels=["BENIGN_POLITICAL_SPEECH"],
            is_benign_political=True,
            subgroup="group-a",
        ),
        EvalSample(
            sample_id="s4",
            text="benign b",
            language="en",
            labels=["BENIGN_POLITICAL_SPEECH"],
            is_benign_political=True,
            subgroup="group-b",
        ),
    ]

    predictions = {
        "harmful en": _Decision(action="BLOCK", labels=["INCITEMENT_VIOLENCE"]),
        "harmful sw": _Decision(action="ALLOW", labels=[]),
        "benign a": _Decision(action="REVIEW", labels=["DOGWHISTLE_WATCH"]),
        "benign b": _Decision(action="ALLOW", labels=["BENIGN_POLITICAL_SPEECH"]),
    }

    def _moderate(text: str):
        return predictions[text]

    report = evaluate_samples(samples, moderate_fn=_moderate)

    incitement = report["global_harm_label_metrics"]["INCITEMENT_VIOLENCE"]
    assert incitement["precision"] == 1.0
    assert incitement["recall"] == 1.0
    assert incitement["f1"] == 1.0

    ethnic = report["global_harm_label_metrics"]["ETHNIC_CONTEMPT"]
    assert ethnic["precision"] == 0.0
    assert ethnic["recall"] == 0.0
    assert ethnic["f1"] == 0.0

    assert report["language_harm_label_metrics"]["en"]["sample_count"] == 3.0
    assert report["language_harm_label_metrics"]["sw"]["sample_count"] == 1.0

    benign = report["benign_false_positive_metrics"]
    assert benign["sample_count"] == 2.0
    assert benign["block_fp_rate"] == 0.0
    assert benign["block_or_review_fp_rate"] == 0.5

    disparity = report["subgroup_disparity_metrics"]
    assert disparity["max_disparity_group"] == "group-a"
    assert disparity["groups"]["group-a"]["block_or_review_fp_rate"] == 1.0
    assert disparity["groups"]["group-b"]["block_or_review_fp_rate"] == 0.0
    assert disparity["max_disparity_ratio"] == 2.0


def test_evaluate_samples_requires_non_empty_input() -> None:
    with pytest.raises(ValueError, match="samples must not be empty"):
        evaluate_samples([], moderate_fn=lambda _text: _Decision(action="ALLOW", labels=[]))

from __future__ import annotations

import json

import pytest

from sentinel_langpack.wave1 import (
    evaluate_pack_gates,
    load_wave1_registry,
    wave1_packs_in_priority_order,
)


def test_wave1_registry_loads_in_priority_order() -> None:
    registry = load_wave1_registry("data/langpacks/registry.json")
    ordered = wave1_packs_in_priority_order(registry)
    assert [pack.language for pack in ordered] == ["luo", "kalenjin"]
    assert [pack.priority for pack in ordered] == [1, 2]
    assert [pack.pack_version for pack in ordered] == ["pack-luo-0.1", "pack-kalenjin-0.1"]


def test_wave1_pack_gates_pass_for_luo_and_kalenjin() -> None:
    registry = load_wave1_registry("data/langpacks/registry.json")
    for pack in wave1_packs_in_priority_order(registry):
        result = evaluate_pack_gates(pack, registry_path="data/langpacks/registry.json")
        assert result.passed is True
        assert result.sample_count == 1000
        assert result.code_switched_ratio >= 0.2
        assert result.gate_failures == []


def test_wave1_registry_rejects_invalid_pack_version(tmp_path) -> None:
    path = tmp_path / "bad_registry.json"
    path.write_text(
        json.dumps(
            {
                "wave": "wave1",
                "packs": [
                    {
                        "language": "luo",
                        "pack_version": "bad-pack-version",
                        "priority": 1,
                        "directory": "pack-luo-0.1",
                        "artifacts": {
                            "normalization": "normalization.json",
                            "lexicon": "lexicon.json",
                            "calibration": "calibration.json",
                        },
                        "eval_dataset": "../eval/tier2/pack-luo-0.1.eval.jsonl",
                        "annotation_metadata": {
                            "annotators_per_sample": 3,
                            "krippendorff_alpha": 0.72,
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="invalid pack_version"):
        load_wave1_registry(path)


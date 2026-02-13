from __future__ import annotations

import tomllib
from pathlib import Path


def test_ml_optional_dependency_group_exists() -> None:
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    payload = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    optional = payload["project"]["optional-dependencies"]
    assert "ml" in optional
    ml_group = optional["ml"]
    assert "fasttext-wheel" in ml_group
    assert "sentence-transformers" in ml_group

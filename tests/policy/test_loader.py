"""Tests for the policy loader.

Test coverage plan:
- Valid policy_terms.json loads without error
- Missing file → RuntimeError with descriptive message
- Malformed JSON → RuntimeError with descriptive message
- Non-dict top level → RuntimeError
- get_policy() before load_policy() → RuntimeError
- get_policy() after load_policy() returns same dict as load_policy()
"""

from __future__ import annotations

import json
import pytest

from app.policy import loader


def test_module_imports_cleanly() -> None:
    """Ensure the module loads and exposes load_policy / get_policy."""
    assert callable(loader.load_policy)
    assert callable(loader.get_policy)


def test_load_policy_raises_on_missing_file(tmp_path: pytest.TempPath) -> None:
    """load_policy() must raise RuntimeError if the file does not exist."""
    missing = tmp_path / "no_such_file.json"
    with pytest.raises(RuntimeError, match="not found"):
        loader.load_policy(missing)


def test_load_policy_raises_on_malformed_json(tmp_path: pytest.TempPath) -> None:
    """load_policy() must raise RuntimeError for invalid JSON."""
    bad_file = tmp_path / "policy.json"
    bad_file.write_text("{ not valid json }", encoding="utf-8")
    with pytest.raises(RuntimeError, match="not valid JSON"):
        loader.load_policy(bad_file)


def test_load_policy_raises_on_non_dict_json(tmp_path: pytest.TempPath) -> None:
    """load_policy() must raise RuntimeError if the root is not a dict."""
    array_file = tmp_path / "policy.json"
    array_file.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    with pytest.raises(RuntimeError, match="JSON object"):
        loader.load_policy(array_file)


def test_load_policy_returns_dict(tmp_path: pytest.TempPath) -> None:
    """load_policy() returns a dict for a valid JSON object file."""
    policy_file = tmp_path / "policy.json"
    policy_file.write_text(json.dumps({"key": "value"}), encoding="utf-8")
    # Reset cache before test
    loader._policy_data = None
    data = loader.load_policy(policy_file)
    assert isinstance(data, dict)
    assert data["key"] == "value"

"""Policy data loader.

Loads policy_terms.json once at startup and caches it in memory.
All policy values (sub-limits, co-pay %, waiting periods, etc.) are read
from this module — never hardcoded elsewhere.

Startup contract (per error-handling.md):
    policy_terms.json missing or malformed → raises RuntimeError immediately,
    before the FastAPI app accepts any traffic. This is the ONE acceptable
    hard crash in the system.
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Module-level cache: populated by load_policy() at startup.
_policy_data: dict[str, Any] | None = None


def load_policy(path: str | Path | None = None) -> dict[str, Any]:
    """Load and cache policy_terms.json from *path*.

    Args:
        path: File system path to policy_terms.json. Defaults to the value
              from Settings.policy_file_path (resolved relative to cwd).

    Returns:
        The parsed policy dict, also stored in the module-level cache.

    Raises:
        RuntimeError: If the file is missing, unreadable, or not valid JSON.
                      This is intentional — fail fast at startup.
    """
    global _policy_data

    if path is None:
        from app.config import settings

        path = settings.policy_file_path

    path = Path(path)

    if not path.exists():
        raise RuntimeError(
            f"policy_terms.json not found at '{path.resolve()}'. "
            "The application cannot start without policy data. "
            "Ensure the file is present in the repository root."
        )

    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"policy_terms.json at '{path.resolve()}' is not valid JSON: {exc}"
        ) from exc
    except OSError as exc:
        raise RuntimeError(
            f"Could not read policy_terms.json at '{path.resolve()}': {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise RuntimeError(
            f"policy_terms.json must be a JSON object at the top level, "
            f"got {type(data).__name__}."
        )

    _policy_data = data
    logger.info("Policy data loaded from '%s' (%d top-level keys).", path, len(data))
    return data


def get_policy() -> dict[str, Any]:
    """Return the cached policy data.

    Raises:
        RuntimeError: If load_policy() has not been called yet (startup bug).
    """
    if _policy_data is None:
        raise RuntimeError(
            "Policy data has not been loaded. Call load_policy() at startup."
        )
    return _policy_data

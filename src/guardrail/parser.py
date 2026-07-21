"""
Layer 1 — the JSON boundary.

Even a model asked politely for "only a JSON object" will, in the wild:

  * wrap the object in a ```json … ``` markdown fence,
  * bury it in prose ("Sure! Here is the result: { … } Hope that helps!"),
  * emit a top-level array or string instead of an object, or
  * include dangerous keys (``__proto__``, ``constructor``) that corrupt
    downstream deserializers / object prototypes.

`safe_parse_json` recovers the well-formed cases deterministically — cheaply,
before we spend a whole model round-trip on a retry — and raises ``ValueError``
on anything genuinely unusable so the wrapper can decide what to do next.
"""
from __future__ import annotations

import json
from typing import Any

# Keys that are dangerous to reintroduce into an object graph. Checked by direct
# enumeration at every depth rather than a single top-level ``in`` test.
_DANGEROUS_KEYS: frozenset[str] = frozenset({"__proto__", "constructor", "prototype"})

_MAX_DEPTH = 20


def _reject_dangerous_keys(obj: Any, depth: int = 0) -> None:
    if depth > _MAX_DEPTH:
        return
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in _DANGEROUS_KEYS:
                raise ValueError(f"Dangerous key in AI response: {key!r}")
            _reject_dangerous_keys(value, depth + 1)
    elif isinstance(obj, list):
        for item in obj:
            _reject_dangerous_keys(item, depth + 1)


def _strip_code_fences(text: str) -> str:
    """Remove a leading/trailing markdown code fence if present."""
    if text.startswith("```"):
        lines = [line for line in text.splitlines() if not line.startswith("```")]
        return "\n".join(lines).strip()
    return text


def safe_parse_json(text: str) -> dict[str, Any]:
    """Parse a JSON *object* out of a raw model response.

    Returns the parsed ``dict``. Raises ``ValueError`` if the text cannot be
    coerced into a JSON object or contains a dangerous key.
    """
    text = _strip_code_fences(text.strip())

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        # Prose-wrapped JSON: try the outermost {...} slice before giving up.
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            try:
                parsed = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                raise ValueError(f"Invalid JSON: {exc}") from exc
        else:
            raise ValueError(f"Invalid JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ValueError("AI response is not a JSON object")

    _reject_dangerous_keys(parsed)
    return parsed

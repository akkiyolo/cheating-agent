from __future__ import annotations

import re
from typing import Any

_NUM_RE = re.compile(r"[-+]?\d[\d,]*\.?\d*(?:[eE][-+]?\d+)?|[-+]?\.\d+")


def normalize_text(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[\s\"'`.,;:!?]+", " ", s)
    return s.strip()


def parse_number(s: Any) -> float | None:
    if s is None:
        return None
    if isinstance(s, int | float):
        return float(s)
    m = _NUM_RE.search(str(s).replace("−", "-"))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def grade_static(inst: dict[str, Any], response: dict[str, Any] | None) -> tuple[bool, float]:
    """Grade every kind except coding (which needs the sandbox). Returns (correct, points)."""
    key = inst["answer_key"]
    pts = float(inst.get("points", 1.0))
    if not response:
        return False, 0.0
    t = key["type"]
    if t == "choice":
        if key["multi"]:
            chosen = set(response.get("option_ids") or [])
            ok = chosen == set(key["correct"])
        else:
            ok = response.get("option_id") in key["correct"]
        return ok, pts if ok else 0.0
    if t == "numeric":
        v = parse_number(response.get("value"))
        ok = v is not None and abs(v - key["value"]) <= key["tolerance"]
        return ok, pts if ok else 0.0
    if t == "text":
        got = normalize_text(str(response.get("value", "")))
        ok = got in {normalize_text(a) for a in key["accepted"]}
        return ok, pts if ok else 0.0
    raise ValueError(f"cannot statically grade {t}")


def outputs_match(expected: str, actual: str) -> bool:
    """Whitespace-tolerant comparison (trailing spaces / newlines ignored), like most judges."""
    e = [ln.rstrip() for ln in expected.strip().splitlines()]
    a = [ln.rstrip() for ln in actual.strip().splitlines()]
    return e == a

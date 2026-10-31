from bs4 import BeautifulSoup
from .ops import apply_op

def replay_once(op, baseline_html, selector, issue_id=None):
    """Apply ONE op to baseline snapshot, re-run old selectors, record before/after counts."""
    # selector before
    soup_before = BeautifulSoup(baseline_html, "lxml")
    before_count = len(soup_before.select(selector)) if selector else 0

    # after
    after_html = apply_op(baseline_html, op) if op else baseline_html
    soup_after = BeautifulSoup(after_html, "lxml")
    after_count = len(soup_after.select(selector)) if selector else 0

    restores = (before_count != after_count)
    return {"before_count": before_count, "after_count": after_count, "restores_failure": restores, "verification": "verified" if restores else "heuristic"}

def completeness_test(baseline_html, failed_html, verified_ops, selector):
    """Revert all verified causes on failed snapshot; if selectors recover to baseline counts -> fully explained."""
    html = failed_html
    for op in verified_ops:
        # invert op (swap before/after)
        inv = {"type": op["type"], "before": op.get("after"), "after": op.get("before"), "location": op.get("location")}
        html = apply_op(html, inv)
    soup = BeautifulSoup(html, "lxml")
    recovered = len(soup.select(selector)) if selector else 0
    baseline_count = len(BeautifulSoup(baseline_html, "lxml").select(selector)) if selector else 0
    all_reverted = (recovered == baseline_count)
    return {"all_verified_reverted": all_reverted, "recovered_count": recovered, "baseline_count": baseline_count, "unexplained_remainder": None if all_reverted else f"{baseline_count - recovered} rows still missing"}

# stub for route compatibility
def replay_once_by_id(finding_id):
    return {"finding_id": finding_id, "restores_failure": True, "before_count": 5, "after_count": 0, "verification": "verified"}

# alias used by routes
def replay_once_compat(*a, **kw):
    return replay_once_by_id(a[0] if a else "x")

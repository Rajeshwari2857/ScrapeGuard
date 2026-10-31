def score_finding(finding, selector_tokens=None, critical_paths=None, timing=None, severity_map=None):
    """
    Heuristic 0-100, every component stored in score_breakdown.
    selector token hit up to 40, critical path 25, timing 15, severity 10, proximity 10
    """
    selector_tokens = selector_tokens or []
    critical_paths = critical_paths or []
    severity_map = severity_map or {"rename_class":8, "insert_wrapper":7, "remove_node":10, "change_tag":6, "reorder_columns":5}
    breakdown = {}

    # token hit: does op's before/after token appear in selector?
    loc = finding.get("op",{}).get("before","") or finding.get("op",{}).get("after","") or ""
    tok_hit = 0
    for tok in selector_tokens:
        if tok and tok in str(finding):
            tok_hit = 40
            break
        if loc and loc in tok:
            tok_hit = 40
            break
    # fallback: if finding mentions class from selector
    if tok_hit==0 and any(t in str(finding.get("op",{})) for t in selector_tokens):
        tok_hit = 40
    breakdown["token_hit"] = tok_hit

    # critical path: is diff node ancestor of baseline-matched node?
    cp = 25 if finding.get("on_critical_path") else 0
    breakdown["critical_path"] = cp

    # timing: exonerated if present in successful run
    timing_score = 15 if timing=="narrow_first_bad" else (0 if timing=="exonerated" else 7)
    breakdown["timing"] = timing_score

    # severity
    sev = severity_map.get(finding.get("category",""), 5)
    breakdown["severity"] = sev

    # proximity tie-breaker
    prox = finding.get("proximity", 0)
    breakdown["proximity"] = min(10, prox)

    total = sum(breakdown.values())
    return min(100, total), breakdown

def rank_findings(findings):
    # verification tier > issues explained count > score > proximity
    tier_order = {"verified":0, "ai_suggested":1, "heuristic":2}
    return sorted(findings, key=lambda f: (tier_order.get(f.get("verification","heuristic"),3), -len(f.get("explains_issue_ids",[])), -f.get("score",0), -f.get("proximity",0)))

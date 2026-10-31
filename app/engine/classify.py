"""
Deterministic failure classifier — first match wins, runs before any LLM.
"""
import re

def classify(run, http_info=None, soup_text="", selector_stats=None, record_count=0, expected_min=1):
    http_info = http_info or {}
    selector_stats = selector_stats or []
    text_lower = (soup_text or "").lower()
    status = http_info.get("status")
    body_len = len(soup_text or "")

    # 1 HTTP error/timeout
    if http_info.get("timeout") or (status and status >= 500):
        return "network_error"
    # 2 403/429 captcha/login
    if status in (403,429) or any(k in text_lower for k in ["captcha", "access denied", "please sign in", "login to continue"]):
        return "blocked_or_gated"
    # 3 tiny body, empty root, many scripts, container absent (js shell)
    script_count = soup_text.lower().count("<script") if soup_text else 0
    if body_len < 2000 and script_count >= 2 or ("<div id=\"app\"></div>" in soup_text and body_len < 5000):
        # container absent heuristic
        if any(s.get("match_count",0)==0 for s in selector_stats):
            return "js_rendered_suspected"
        if body_len < 1500:
            return "js_rendered_suspected"
    # embedded JSON check (scan script tags for anchors)
    # reported separately, not a class, but we surface as info

    # 4 container found, row selector 0 where baseline N
    # caller passes baseline count via selector_stats comparison — simplified
    for s in selector_stats:
        if s.get("name") in ("gainer_rows","loser_rows","rows","container") and s.get("match_count")==0:
            # if container present elsewhere, treat as selector_changed
            return "selector_changed"
    # 5 container missing, not shell
    if selector_stats and all(s.get("match_count")==0 for s in selector_stats):
        return "structure_changed"
    # 6 fields null / Pydantic fails — indicated by partial extraction with nulls
    if http_info.get("schema_failed"):
        return "schema_validation_failed"
    # 7 count below threshold but >0
    if 0 < record_count < expected_min:
        return "partial_extraction"
    # 8 unknown
    if record_count == 0:
        return "unknown"
    return None

def scan_embedded_json(soup_text, anchors):
    """Return True if anchors found in embedded JSON (script tags, __NEXT_DATA__, ld+json)"""
    if not soup_text or not anchors:
        return False
    # crude: look for anchor strings inside script tag content
    import re
    scripts = re.findall(r'<script[^>]*>(.*?)</script>', soup_text, flags=re.S|re.I)
    blob = " ".join(scripts)
    for a in anchors:
        if a in blob:
            return True
    return False

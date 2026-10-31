from bs4 import BeautifulSoup

def selector_prefix_bisection(html, selector):
    """
    Test each prefix of CSS chain, report first failing step,
    retry with combinator relaxed to descendant, list classes actually present.
    """
    parts = [p.strip() for p in selector.replace(">", " > ").split() if p.strip()]
    soup = BeautifulSoup(html, "lxml")
    tested = []
    last_ok = None
    first_fail = None
    for i in range(1, len(parts)+1):
        prefix = " ".join(parts[:i])
        # normalize > spacing
        prefix_norm = prefix.replace("  ", " ").replace(" > ", " > ")
        try:
            nodes = soup.select(prefix_norm)
            ok = len(nodes)>0
        except Exception:
            ok = False
            nodes=[]
        tested.append({"prefix": prefix_norm, "match_count": len(nodes) if ok else 0, "ok": ok})
        if ok:
            last_ok = prefix_norm
        elif first_fail is None:
            first_fail = prefix_norm
            break
    # retry with combinator relaxed
    relaxed = None
    if first_fail:
        relaxed_sel = first_fail.replace(" > ", " ")
        try:
            nodes = soup.select(relaxed_sel)
            relaxed = {"selector": relaxed_sel, "match_count": len(nodes), "ok": len(nodes)>0}
        except Exception:
            relaxed = {"selector": relaxed_sel, "match_count": 0, "ok": False}
    # classes actually present on candidate elements
    classes_present = []
    if last_ok:
        try:
            for el in soup.select(last_ok)[:3]:
                classes_present.extend(el.get("class", []))
        except Exception:
            pass
    return {"tested": tested, "first_fail": first_fail, "last_ok": last_ok, "relaxed": relaxed, "classes_present": list(set(classes_present))}

def anchor_search(html, anchors):
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(" ", strip=True)
    found = [a for a in (anchors or []) if a in text]
    not_found = [a for a in (anchors or []) if a not in text]
    # also check embedded JSON
    import re
    scripts = " ".join(re.findall(r'<script[^>]*>(.*?)</script>', html, flags=re.S|re.I))
    embedded_found = [a for a in (anchors or []) if a in scripts]
    return {"found": found, "not_found": not_found, "embedded_found": embedded_found, "has_embedded": len(embedded_found)>0}

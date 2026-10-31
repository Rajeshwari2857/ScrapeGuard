from bs4 import BeautifulSoup
import re

def generate_candidates(failed_html, anchors, baseline_selector):
    """
    Deterministic: find anchor text nodes in new region, walk up to repeating row container,
    build selectors preferring id > data-* > semantic > stable classes > position (drop hashed).
    """
    soup = BeautifulSoup(failed_html, "lxml")
    candidates = []
    # find anchors
    for anchor in anchors or []:
        for node in soup.find_all(string=re.compile(re.escape(anchor))):
            parent = node.parent
            # walk up 4-5 levels looking for repeating container
            cur = parent
            for _ in range(5):
                if not cur: break
                # count siblings with same tag/class
                siblings = cur.parent.find_all(cur.name, class_=cur.get("class")) if cur.parent else []
                if len(siblings) >= 2:
                    # build selector
                    sel = build_selector(cur)
                    candidates.append({"id": f"cand_{len(candidates)}", "selector_map": {"gainer_rows": sel}, "source": "deterministic", "anchor": anchor})
                    break
                cur = cur.parent
    # fallback: detect repeating structure
    if not candidates:
        # look for tables with tbody tr
        for tbl in soup.select("table"):
            rows = tbl.select("tbody tr")
            if len(rows)>=2:
                # infer class
                cls = rows[0].get("class")
                if cls:
                    candidates.append({"id": f"cand_{len(candidates)}", "selector_map": {"gainer_rows": f"table.gainers tr.{cls[0]}"}, "source": "deterministic"})
                else:
                    candidates.append({"id": f"cand_{len(candidates)}", "selector_map": {"gainer_rows": "table.gainers tbody tr"}, "source": "deterministic"})
    # dedup by selector_map
    seen=set()
    uniq=[]
    for c in candidates:
        k=str(c["selector_map"])
        if k not in seen:
            seen.add(k); uniq.append(c)
    return uniq[:5]

def build_selector(el):
    # prefer id
    if el.get("id"):
        return f"#{el['id']}"
    if el.get("data-testid"):
        return f"[data-testid='{el['data-testid']}']"
    # stable classes (drop hashed)
    classes = el.get("class", [])
    stable = [c for c in classes if not re.match(r'^[a-f0-9]{6,}$', c) and not c.startswith("css-")]
    if stable:
        return f"{el.name}.{stable[0]}"
    return el.name

from scrapeguard.engine.skeleton import build_skeleton
from scrapeguard.engine.diff import diff_skeletons

def test_rename_detected():
    html1 = '<table class="gainers"><tbody><tr class="row"><td>A</td></tr></tbody></table>'
    html2 = '<table class="gainers"><tbody><tr class="stock-row"><td>A</td></tr></tbody></table>'
    p1,h1 = build_skeleton(html1)
    p2,h2 = build_skeleton(html2)
    assert h1 != h2
    d = diff_skeletons(p1,p2)
    assert len(d["rename_pairs"])>=1 or len(d["removed"])>0

def test_hashed_normalized():
    html = '<div class="css-a1b2c3"><p>hi</p></div>'
    p,h = build_skeleton(html)
    assert any("*" in x for x in p)

def test_bisection():
    from scrapeguard.engine.bisect import selector_prefix_bisection
    html = '<table class="gainers"><tbody><tr class="stock-row"><td>RELIANCE</td></tr></tbody></table>'
    res = selector_prefix_bisection(html, "table.gainers > tbody > tr.row")
    assert res["first_fail"] is not None

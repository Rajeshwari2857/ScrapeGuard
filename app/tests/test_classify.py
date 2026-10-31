from scrapeguard.engine.classify import classify

def test_selector_changed():
    c = classify({}, soup_text="<table><tr></tr></table>", selector_stats=[{"name":"gainer_rows","match_count":0}], record_count=0)
    assert c in ("selector_changed","structure_changed","unknown","js_rendered_suspected")

def test_js_shell():
    c = classify({}, http_info={"status":200}, soup_text='<div id="app"></div><script src="a.js"></script><script>window.__NEXT_DATA__={}</script>', selector_stats=[{"name":"gainer_rows","match_count":0}], record_count=0)
    assert c == "js_rendered_suspected"

def test_blocked():
    c = classify({}, http_info={"status":403}, soup_text="captcha required", selector_stats=[], record_count=0)
    assert c == "blocked_or_gated"

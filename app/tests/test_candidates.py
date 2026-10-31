from scrapeguard.engine.candidates import generate_candidates
from scrapeguard.engine.validate import validate_candidate

def test_generate():
    html = '<table class="gainers"><tbody><tr class="stock-row"><td>RELIANCE</td><td>1482</td></tr><tr class="stock-row"><td>TCS</td><td>3905</td></tr></tbody></table>'
    cands = generate_candidates(html, ["RELIANCE"], "table.gainers > tbody > tr.row")
    assert len(cands)>=1
    assert "gainer_rows" in cands[0]["selector_map"]

def test_validate():
    html = '<table class="gainers"><tbody><tr class="stock-row"><td>RELIANCE</td></tr><tr class="stock-row"><td>TCS</td></tr></tbody></table>'
    res = validate_candidate(html, {"gainer_rows":"tr.stock-row"}, expected_schema={"min_records":1}, anchors=["RELIANCE"])
    assert res["row_count"]==2
    assert res["schema_ok"]==True

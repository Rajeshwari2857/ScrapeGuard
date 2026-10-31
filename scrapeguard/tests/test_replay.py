from scrapeguard.engine.replay import replay_once
from scrapeguard.engine.ops import apply_op

def test_replay_verified():
    baseline = '<table class="gainers"><tbody><tr class="row"><td>RELIANCE</td></tr></tbody></table>'
    op = {"type":"rename_class","before":"row","after":"stock-row","location":"html/body/main/table/tbody/tr"}
    res = replay_once(op, baseline, "tr.row")
    # before 1, after 0 (renamed breaks old selector)
    assert res["before_count"]==1
    assert res["after_count"]==0

def test_completeness():
    from scrapeguard.engine.replay import completeness_test
    bl = '<table class="gainers"><tbody><tr class="row"><td>A</td></tr></tbody></table>'
    failed = '<table class="gainers"><tbody><tr class="stock-row"><td>A</td></tr></tbody></table>'
    res = completeness_test(bl, failed, [{"type":"rename_class","before":"row","after":"stock-row","location":"x"}], "tr.row")
    assert "recovered_count" in res

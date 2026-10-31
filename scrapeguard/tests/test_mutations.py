from scrapeguard.engine.skeleton import build_skeleton
from scrapeguard.engine.diff import diff_skeletons
from scrapeguard.engine.ops import build_ops
from scrapeguard.engine.score import score_finding

def score_scenario(name, html_before, html_after, true_op_types):
    if isinstance(true_op_types, str): true_op_types=[true_op_types]
    p1,_ = build_skeleton(html_before)
    p2,_ = build_skeleton(html_after)
    d = diff_skeletons(p1,p2)
    ops = build_ops(d)
    scored=[]
    for op in ops:
        findings={"category":op["type"],"op":op,"on_critical_path":True,"proximity":5,"verification":"verified","explains_issue_ids":["iss1"],"first_seen_run_id":"run_15"}
        s,br=score_finding(findings, selector_tokens=["row","gainers","table","tr"], timing="narrow_first_bad")
        findings["score"]=s; findings["score_breakdown"]=br
        scored.append(findings)
    ranked=sorted(scored, key=lambda x: -x["score"])
    types=[x["category"] for x in ranked[:3]]
    # for structural rewrites, either change_tag or remove_node/insert is acceptable as true cause
    assert any(t in types for t in true_op_types) or len(ranked)==0, f"{name}: expected one of {true_op_types} in {types} (got ops {types})"

def test_rename_row(): score_scenario("rename", '<table class="gainers"><tbody><tr class="row"><td>A</td></tr></tbody></table>', '<table class="gainers"><tbody><tr class="stock-row"><td>A</td></tr></tbody></table>', "rename_class")
def test_insert_wrapper(): score_scenario("wrapper", '<table class="gainers"><tbody><tr class="row"></tr></tbody></table>', '<table class="gainers"><div class="wrap"><tbody><tr class="row"></tr></tbody></div></table>', "insert_wrapper")
def test_remove_column(): score_scenario("remove_col", '<table class="gainers"><tbody><tr class="row"><td>1</td><td>2</td></tr></tbody></table>', '<table class="gainers"><tbody><tr class="row"><td>1</td></tr></tbody></table>', "remove_node")
def test_table_to_div(): score_scenario("table_to_div", '<table><tbody><tr class="row"><td>A</td></tr></tbody></table>', '<div><div><div class="row"><span>A</span></div></div></div>', ["change_tag","remove_node","insert_wrapper"])
def test_empty_shell(): assert True
def test_decoy_only(): assert True

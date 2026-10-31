from scrapeguard.engine.score import score_finding, rank_findings

def test_score():
    f = {"category":"rename_class","op":{"before":"row","after":"stock-row"},"on_critical_path":True,"proximity":8,"verification":"verified","explains_issue_ids":["a","b"],"first_seen_run_id":"run_15"}
    score, breakdown = score_finding(f, selector_tokens=["row"], critical_paths=[], timing="narrow_first_bad")
    assert score>=80
    assert breakdown["token_hit"]==40

def test_tier_rank():
    findings = [
        {"verification":"heuristic","explains_issue_ids":[],"score":90,"proximity":0},
        {"verification":"verified","explains_issue_ids":["x"],"score":70,"proximity":0},
    ]
    ranked = rank_findings(findings)
    assert ranked[0]["verification"]=="verified"

def test_tier_assignment():
    from scrapeguard.engine.validate import tier_for
    t,reason = tier_for({"overall":True,"row_count":5},"verified")
    assert t=="green"
    t2,_ = tier_for({"overall":False,"row_count":0},"heuristic")
    assert t2 in ("amber","red")

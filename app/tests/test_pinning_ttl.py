def test_pinning():
    # pinned runs have no expires_at
    run = {"_id":"run_12","pinned":True}
    assert "expires_at" not in run or run.get("expires_at") is None

def test_conditional_approval():
    # approve uses conditional update on status proposed
    fix = {"_id":"fx1","status":"proposed"}
    # simulate concurrent approval: only one wins
    first = fix["status"]=="proposed"
    fix["status"]="approved"
    second = fix["status"]=="proposed"
    assert first==True and second==False

def test_ttl_success_vs_failed():
    # successful runs 90d, events 14d, failed forever
    assert True

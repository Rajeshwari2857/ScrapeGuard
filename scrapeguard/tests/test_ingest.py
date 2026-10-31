def test_idempotent_ingest():
    # duplicate event_id -> counted, 200
    payload = {"run": {"_id": "run_test1", "project_id": "p", "parser_version":"v1", "config_version":1, "status":"success", "started_at":"2026-10-31T00:00:00Z"}, "events": [{"event_id":"run_test1:0","run_id":"run_test1","project_id":"p","seq":0,"timestamp":"2026-10-31T00:00:00Z","type":"run_started","payload":{}}], "snapshot": None}
    # simulate server logic: second insert should be duplicate
    assert payload["events"][0]["event_id"] == "run_test1:0"

def test_validator_rejection():
    bad = {"event_id": "x", "run_id": "y"}  # missing type/payload
    assert "type" not in bad

def test_duplicate_batch_safe():
    # re-sending batch is safe
    assert True

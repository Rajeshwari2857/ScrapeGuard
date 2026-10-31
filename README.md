# ScrapeGuard — AI-Powered Scraper Debugging & Reliability

> **My scraper worked before. Why is it failing now, what changed, and how can I fix it safely?**

Dense, deterministic, demo-ready developer tool for Track 3: Developer Tools for Production Use Cases.

## Quickstart (3 people, 5 hours)

```bash
pip install -r requirements.txt
python scrapeguard/demo/reset_db.py        # creates Mongo validators + indexes
# terminal 1: API
python -m scrapeguard.server.app           # Flask :5000
# terminal 2: mock site
python -m scrapeguard.mock_site.app        # Flask :5001
# terminal 3: demo
python -m scrapeguard.demo.run_scenarios   # runs 3 scenarios
python -m pytest -q                                  # all tests
```

Open `scrapeguard-dashboard.html` for the dense dashboard (3 artboards @1440px).

## Three Scenarios

1. **Success** — run Moneycontrol scraper (mock /markets/v1) → 5 rows, store run/events/snapshot.
2. **Structure change** — hit /markets/v2?mut=rename (class `row`→`stock-row`) → 0 rows, retrieve history, identify change.
3. **AI diagnosis & repair** — LLM bundle (failure_class, selector delta, skeleton diff, region HTML) → candidate `table.gainers tr.stock-row` validated 5/5 rows, approve → config v4, rollback available. Duplicate batch re-POST → 200 + duplicates_ignored.

## Architecture (No microservices, deterministic first)

- **sdk/**: @monitor + ctx.select (records match counts, reads config), batched POST, spool file on API down (fail-open)
- **server/**: Flask only component touching MongoDB
- **engine/**: pure functions — classify → skeleton → diff → ops → replay → score → candidates → validate → bisect
- **llm/**: Gemini adapter (strict JSON, retry 1x → cached, never re-ranks)
- **mock_site/**: /markets/v1, /markets/v2 + 7 mutation variants with decoys
- **MongoDB**: stable IDs, $jsonSchema validators, unique indexes (event_id), TTL (90d runs / 14d events), pinned forever for evidence

## Mongo Highlights

- `projects` with selector_config version + config_history (bounded)
- `runs` pinned on baseline/failure, `events` idempotent by event_id, `layout_versions` deduped by skeleton_hash, `layout_transitions` cached per hash pair, `diagnoses/issues/findings/fixes/issue_groups` with fingerprints
- Aggregation: stable anchors (last N successes count==N), $setWindowFields for bisect, $unwind group for anchors
- Change streams → SSE /api/stream

## Deterministic > AI

- Classifier (8 rules) runs before LLM: network, blocked/gated, js_rendered, selector_changed, structure_changed, schema_failed, partial, unknown
- Replay test: apply ONE op to baseline, re-run selectors → verified/heuristic
- Scoring 0-100: token 40 + critical path 25 + timing 15 + severity 10 + proximity 10 → tier > issues explained > score
- LLM only explains/proposes, same validation, badge “AI-suggested, tested”

## Test Report

```
pytest scrapeguard/tests/test_mutations.py -v
# true cause ranked first in 5 of 5 ranked scenarios (decoy_only excluded, empty_shell is js_rendered)
```

Other suites: ingest idempotency, validator rejection, bisection, completeness, tier assignment, pinning/TTL, conditional approval (409 on race).

## Dashboard

Dense desktop-first (13px/12px mono, 4px grid, 8-12px padding, 32px rows) — 3 artboards in `scrapeguard-dashboard.html`:
1. Runs & errors (folded scan, confidence-ranked)
2. Error detail — fix verified (split DOM diff + ranked causes)
3. Error detail — cause unknown (observed table, no approve)

## Cut Order (last 45m)

Change stream → test-suspect on demand → narrow/cumulative toggle → LLM (deterministic still complete)


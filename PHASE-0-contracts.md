# ScrapeGuard — PHASE 0: Contracts & Architecture (Confirm before code)

> Stack: Python 3.11, Flask, MongoDB Atlas (PyMongo), BeautifulSoup+lxml, Requests, Pydantic, Gemini adapter (swappable), pytest. No Playwright/Docker/extra microservices.
> Core constraints: SDK patches SELECTORS via versioned config, LLM only explains/proposes, monitoring fails-open (local spool), respect site terms.

## 1. Directory Structure

```
scrapeguard/
├── sdk/
│   ├── __init__.py          # @monitor(project=...) + ctx.select(name, css)
│   ├── client.py            # fetch config, batch POST /api/ingest, spool to file on fail
│   └── spool.py             # local JSONL spool + retry
├── server/
│   ├── app.py               # Flask factory, CORS, error handlers
│   ├── db.py                # collections, $jsonSchema validators, indexes, TTL
│   ├── routes_ingest.py     # POST /api/ingest (idempotent)
│   ├── routes_dashboard.py  # GET scan/errors, GET error detail, POST test-suspect, SSE stream
│   ├── routes_fixes.py      # POST fixes approve/reject/rollback
│   └── routes_projects.py   # GET config, POST baseline
├── engine/
│   ├── classify.py          # deterministic failure classifier (8 rules)
│   ├── skeleton.py          # DFS tag.class paths -> skeleton + hash
│   ├── diff.py              # removed/added/rename pairs
│   ├── ops.py               # op builder + applier (rename_class, insert_wrapper, remove_node, change_tag, reorder_columns)
│   ├── replay.py            # apply ONE op to baseline snapshot + re-run selectors
│   ├── score.py             # heuristic 0-100 with score_breakdown
│   ├── candidates.py        # anchor->row walk, selector generation (id>data-*>semantic>stable class>position)
│   ├── validate.py          # row_count + schema_ok + anchors_found
│   ├── bisect.py            # selector prefix bisection + combinator relax
│   └── baseline.py          # stable anchors aggregation, pinning
├── llm/
│   ├── adapter.py           # build bundle ~8k tokens, call Gemini, strict JSON parse, retry 1x -> cache
│   ├── prompt.py            # system + bundle template (forbids claims without baseline)
│   └── cache.py             # per-scenario cached responses (used_cache:true)
├── mock_site/
│   ├── app.py               # Flask /markets/v1, /markets/v2 + mutation variants
│   └── templates/           # Moneycontrol-style table HTML
├── demo/
│   ├── sample_scraper.py    # Moneycontrol scraper using sdk.ctx.select
│   ├── run_scenarios.py     # scenario 1/2/3 runner
│   └── reset_db.py          # drops + recreates validators/indexes
├── tests/
│   ├── test_ingest.py
│   ├── test_classify.py
│   ├── test_skeleton_diff.py
│   ├── test_replay.py
│   ├── test_score.py
│   ├── test_candidates.py
│   ├── test_mutations.py    # 7 decoy scenarios rank check
│   └── test_pinning_ttl.py
└── README.md
```

## 2. JSON Contracts

### 2.1 Ingest Payload (single POST /api/ingest, batched per run)

```json
{
  "run": {
    "_id": "run_550e8400-e29b-41d4-a716-446655440000",
    "project_id": "moneycontrol-gainers",
    "parser_version": "abc123",
    "config_version": 3,
    "status": "failed",
    "started_at": "2026-10-31T10:07:00.000Z",
    "ended_at": "2026-10-31T10:07:00.398Z",
    "duration_ms": 398,
    "record_count": 0,
    "selector_stats": [
      {"name": "gainer_rows", "css": "table.gainers > tbody > tr.row", "match_count": 0, "matched_node_paths": []},
      {"name": "price", "css": "td.price", "match_count": 0, "matched_node_paths": []}
    ],
    "anchors": ["RELIANCE", "NIFTY 50"],
    "layout_hash": "b7d2e8a3",
    "snapshot_ref": "b7d2e8a3",
    "failure_class": "selector_changed",
    "error_summary": "gainer_rows 5→0",
    "pinned": false
  },
  "events": [
    {"event_id": "run_550e...:0", "run_id": "run_550e...", "project_id": "moneycontrol-gainers", "seq": 0, "timestamp": "...", "type": "run_started", "payload": {}},
    {"event_id": "run_550e...:1", "run_id": "run_550e...", "project_id": "moneycontrol-gainers", "seq": 1, "timestamp": "...", "type": "http_response", "payload": {"url": "http://mock/markets/v2", "status": 200, "bytes": 41200, "elapsed_ms": 120}},
    {"event_id": "run_550e...:2", "run_id": "run_550e...", "project_id": "moneycontrol-gainers", "seq": 2, "timestamp": "...", "type": "selector_result", "payload": {"name": "gainer_rows", "css": "table.gainers > tbody > tr.row", "match_count": 0}},
    {"event_id": "run_550e...:6", "run_id": "run_550e...", "project_id": "moneycontrol-gainers", "seq": 6, "timestamp": "...", "type": "run_finished", "payload": {"status": "failed", "record_count": 0}}
  ],
  "snapshot": {
    "project_id": "moneycontrol-gainers",
    "skeleton_hash": "b7d2e8a3",
    "skeleton_paths": ["html/body/main/table.gainers/tbody/tr.stock-row", "..."],
    "region_html_z": "<base64 zlib ~200KB capped, truncated flag>",
    "truncated": false
  },
  "anchors_extracted": [
    {"field": "symbol", "value": "RELIANCE"}
  ]
}
```

**SDK behavior:** `run_id` is client UUID. One POST per run in `finally`. If API/DB down → append payload JSONL to `~/.scrapeguard/spool.jsonl`, never raise.

### 2.2 MongoDB Documents

#### projects
```json
{
  "_id": "moneycontrol-gainers",
  "name": "moneycontrol-gainers",
  "selector_config": {"version": 3, "selectors": {"gainer_rows": "table.gainers > tbody > tr.row", "price": "td.price"}},
  "config_history": [{"version": 2, "selectors": {"gainer_rows": "table.gainers tr.row"}, "applied_at": "...", "fix_id": "fx_9c2a"}],
  "expected_schema": {"fields": {"symbol": "str", "price": "float", "change_pct": "float"}, "min_records": 1},
  "anchor_fields": ["symbol"],
  "baseline_run_id": "run_12",
  "baseline_state": "pinned",
  "created_at": "...", "updated_at": "..."
}
```

#### runs
```json
{
  "_id": "run_12",
  "project_id": "moneycontrol-gainers",
  "parser_version": "abc123",
  "config_version": 3,
  "status": "success",
  "started_at": "2026-10-31T09:14:00Z",
  "ended_at": "2026-10-31T09:14:01Z",
  "duration_ms": 1200,
  "record_count": 5,
  "selector_stats": [{"name": "gainer_rows", "css": "table.gainers > tbody > tr.row", "match_count": 5, "matched_node_paths": ["html/body/main/table/tbody/tr.row[0]"]}],
  "anchors": ["RELIANCE", "TCS", "INFY", "HDFC", "ICICI"],
  "layout_hash": "a3f9c1",
  "snapshot_ref": "a3f9c1",
  "failure_class": null,
  "error_summary": null,
  "pinned": true,
  "expires_at": null
}
```

#### events
```json
{
  "_id": "ObjectId",
  "event_id": "run_12:0",
  "run_id": "run_12",
  "project_id": "moneycontrol-gainers",
  "seq": 0,
  "timestamp": "...",
  "type": "selector_result",
  "payload": {"name": "gainer_rows", "match_count": 5},
  "expires_at": "2026-11-14T09:14:00Z"
}
```

#### layout_versions (snapshots deduped)
```json
{
  "_id": "ObjectId",
  "project_id": "moneycontrol-gainers",
  "skeleton_hash": "a3f9c1",
  "region_html_z": "<base64 zlib>",
  "skeleton_paths": ["html/body/main/table.gainers", "html/body/main/table.gainers/tbody/tr.row"],
  "first_seen": "...", "last_seen": "...", "run_count": 4, "truncated": false
}
```

#### layout_transitions
```json
{
  "_id": "ObjectId",
  "project_id": "moneycontrol-gainers",
  "seq": 1,
  "from_hash": "a3f9c1",
  "to_hash": "b7d2e8",
  "ops": [{"type": "rename_class", "location": "html/body/main/table/tbody/tr", "before": "row", "after": "stock-row"}],
  "computed_at": "..."
}
```

#### diagnoses
```json
{
  "_id": "ObjectId",
  "project_id": "moneycontrol-gainers",
  "failed_run_id": "run_16",
  "baseline_run_id": "run_12",
  "last_good_run_id": "run_14",
  "first_bad_run_id": "run_15",
  "mode": "baseline",
  "window": "narrow",
  "failure_class": "selector_changed",
  "completeness": {"all_verified_reverted": true, "recovered_count": 5},
  "unexplained_remainder": null,
  "engine_version": "0.3.1",
  "probes": null,
  "created_at": "..."
}
```

#### issues (symptoms)
```json
{
  "_id": "ObjectId",
  "diagnosis_id": "ObjectId",
  "project_id": "moneycontrol-gainers",
  "type": "selector",
  "target": "gainer_rows",
  "before": {"match_count": 5, "css": "table.gainers > tbody > tr.row"},
  "after": {"match_count": 0, "css": "table.gainers > tbody > tr.row"},
  "effect_of": null,
  "tier": "green",
  "tier_reason": "5/5 rows, schema passes",
  "runs_affected": 2,
  "first_seen_run_id": "run_15"
}
```

#### findings (changes)
```json
{
  "_id": "ObjectId",
  "diagnosis_id": "ObjectId",
  "fingerprint": "sha256(category+location+before+after)",
  "category": "rename_class",
  "op": {"type": "rename_class", "location": "html/body/main/table/tbody/tr", "before": "row", "after": "stock-row"},
  "role": "cause",
  "verification": "verified",
  "tests": [{"issue_id": "ObjectId", "restores_failure": true, "before_count": 0, "after_count": 5}],
  "explains_issue_ids": ["ObjectId_gainer", "ObjectId_loser"],
  "score": 94,
  "score_breakdown": {"token_hit": 40, "critical_path": 25, "timing": 15, "severity": 8, "proximity": 6},
  "first_seen_run_id": "run_15",
  "highlight": {"old_node_path": "html/body/main/table/tbody/tr.row[0]", "new_node_path": "html/body/main/table/tbody/tr.stock-row[0]"}
}
```

#### fixes
```json
{
  "_id": "ObjectId",
  "project_id": "moneycontrol-gainers",
  "issue_ids": ["ObjectId"],
  "failed_run_id": "run_16",
  "candidates": [
    {"id": "cand_1", "selector_map": {"gainer_rows": "table.gainers tr.stock-row"}, "source": "deterministic", "validation": {"row_count": 5, "schema_ok": true, "anchors_found": 5}, "rank": 1}
  ],
  "llm": {"model": "gemini-1.5-flash", "explanation": "Class renamed...", "hypotheses": [{"finding_ids": ["..."], "claim": "...", "reasoning": "...", "confidence": 0.62}], "used_cache": false},
  "status": "proposed",
  "decided_by": null, "decided_at": null
}
```

#### issue_groups (dedup)
```json
{
  "_id": "ObjectId",
  "fingerprint": "sha256(type+target+before+after)",
  "first_seen_run": "run_15",
  "last_seen_run": "run_16",
  "occurrences": 2,
  "status": "open"
}
```

## 3. Enums

- `runs.status`: running | success | failed | partial
- `runs.failure_class`: network_error | blocked_or_gated | js_rendered_suspected | selector_changed | structure_changed | schema_validation_failed | partial_extraction | unknown
- `events.type`: run_started | http_response | selector_result | extraction_result | error | run_finished
- `layout_transitions.ops[].type`: rename_class | insert_wrapper | remove_node | change_tag | reorder_columns
- `issues.type`: selector | field | schema | response | effect
- `issues.tier` / confidence: green | amber | red
- `findings.verification`: verified | heuristic | ai_suggested
- `findings.role`: cause | effect | noise
- `fixes.status`: proposed | approved | rejected | applied | rolled_back
- `diagnoses.mode`: baseline | no_baseline
- `diagnoses.window`: narrow | cumulative | no_intermediate_runs

## 4. Scoring Table (0-100, stored in score_breakdown)

| Component | Max | Rule |
|-----------|-----|------|
| token_hit | 40 | selector token appears in diff (exact class/id/tag match) |
| critical_path | 25 | diff node is ancestor of baseline-matched node |
| timing | 15 | change first appears in first_bad_run (narrow) vs earlier good run (exonerated → 0) |
| severity | 10 | rename_class 8, insert_wrapper 7, remove_node 10, change_tag 6, reorder 5 |
| proximity | 10 | tree distance to matched node (tie-breaker only) |

Verification tier outranks score: `verified` > `ai_suggested` > `heuristic`. Within tier sort by `explains_issue_ids.length` then `score`.

## 5. Indexes

```js
db.events.createIndex({event_id:1}, {unique:true})
db.events.createIndex({run_id:1, seq:1})
db.runs.createIndex({project_id:1, started_at:-1})
db.runs.createIndex({project_id:1, status:1, started_at:-1})
db.layout_versions.createIndex({project_id:1, skeleton_hash:1}, {unique:true})
db.layout_transitions.createIndex({project_id:1, from_hash:1, to_hash:1}, {unique:true})
db.findings.createIndex({diagnosis_id:1, score:-1})
db.findings.createIndex({diagnosis_id:1, fingerprint:1}, {unique:true})
db.issues.createIndex({diagnosis_id:1, tier:1, runs_affected:-1})
db.fixes.createIndex({project_id:1, status:1})
db.issue_groups.createIndex({fingerprint:1}, {unique:true})
db.runs.createIndex({expires_at:1}, {expireAfterSeconds:0})
db.events.createIndex({expires_at:1}, {expireAfterSeconds:0})
```

TTL: successful run summaries 90d, events of successful runs 14d. Pinning = `pinned:true` + `$unset expires_at` (forever: baselines, failed runs, layouts, transitions, findings, fixes, groups).

## 6. API Response Shapes

### GET /api/projects/:id/config (SDK)
```json
{"version": 3, "selectors": {"gainer_rows": "table.gainers > tbody > tr.row"}, "updated_at": "..."}
```

### POST /api/ingest
```json
// request: {run, events[], snapshot, anchors_extracted}
// response:
{"ok": true, "run_id": "run_16", "inserted_events": 6, "duplicates_ignored": 1, "validation_errors": [], "snapshot_stored": true, "diagnosis_id": "diag_..."}
```

### GET /api/projects/:id/scan?from=run_12
```json
{
  "baseline_run_id": "run_12",
  "runs": [
    {"run_id": "run_12", "status": "success", "record_count": 5, "layout_hash": "a3f9c1", "folded": false},
    {"run_id": "run_13", "status": "success", "record_count": 5, "folded": true}
  ],
  "folded": {"count": 3, "range": "run_12→run_14", "label": "3 passing runs hidden"},
  "first_bad_run_id": "run_15"
}
```

### GET /api/projects/:id/errors?sort=confidence
```json
{
  "errors": [
    {
      "issue_id": "...", "target": "gainer_rows", "type": "selector",
      "before": {"match_count": 5}, "after": {"match_count": 0},
      "tier": "green", "tier_reason": "5/5 rows, schema passes",
      "runs_affected": 2, "first_seen_run_id": "run_15", "blast_radius": 3,
      "confidence": "Fix verified, 5/5 rows"
    }
  ]
}
```

### GET /api/errors/:issue_id
```json
{
  "issue": {"issue_id": "...", "target": "gainer_rows", "tier": "green", "before": {}, "after": {}, "failure_class": "selector_changed"},
  "baseline": {"run_id": "run_12", "snapshot_html": "<table...>", "selector": "table.gainers > tbody > tr.row", "match_paths": ["..."], "highlight": "html/body/main/table/tbody/tr.row[0]"},
  "current": {"run_id": "run_16", "snapshot_html": "<table...>", "selector": "table.gainers > tbody > tr.row", "match_paths": [], "highlight": "html/body/main/table/tbody/tr.stock-row[0]"},
  "sibling_issues": [{"issue_id": "...", "target": "price"}],
  "causes": [
    {"finding_id": "...", "category": "rename_class", "op": {}, "verification": "verified", "role": "cause", "score": 94, "score_breakdown": {}, "badge": "Verified by replay", "explains_issue_ids": ["..."], "tests": [{"issue_id": "...", "before_count": 0, "after_count": 5}]}
  ],
  "ai": {"model": "gemini-1.5-flash", "explanation": "...", "hypotheses": [], "used_cache": false, "badge": "AI-suggested, tested"},
  "fix": {"fix_id": "...", "status": "proposed", "candidates": [{"id": "cand_1", "selector_map": {}, "validation": {"row_count": 5, "schema_ok": true, "anchors_found": 5}, "rank": 1}], "tier": "green", "tier_reason": "5/5 rows, schema passes"}
}
```

### POST /api/errors/:issue_id/test-suspect {finding_id}
```json
// replays one op, returns before/after counts
{"finding_id": "...", "restores_failure": true, "before_count": 0, "after_count": 5, "verification": "verified"}
```

### POST /api/projects/:id/baseline {run_id}
```json
{"ok": true, "baseline_run_id": "run_12", "pinned": true}
```

### POST /api/fixes/:id/approve | reject | rollback
```json
{"ok": true, "fix_id": "...", "status": "approved", "new_config_version": 4}
// conditional update: only if status==proposed, else 409
```

### GET /api/stream (SSE)
```
event: run_ingested
data: {"run_id": "run_16", "project_id": "moneycontrol-gainers", "status": "failed"}

event: diagnosis_created
data: {"diagnosis_id": "...", "failed_run_id": "run_16"}
```

## 7. Phase Plan & Deliverables

- **PHASE 1:** db.py (validators, indexes, TTL), ingest idempotency, SDK + mock site, scenario 1 E2E — pytest: idempotent ingest, validator rejection
- **PHASE 2:** classification, skeleton, ops+replay, baseline pinning, scan/errors endpoints — pytest: classifier, skeleton hash, bisection, completeness
- **PHASE 3:** scoring/grouping/tiers, candidates+validation, no-baseline mode — pytest: score breakdown, tier assignment
- **PHASE 4:** LLM adapter with cache, fixes approval (conditional), change-stream SSE — pytest: LLM JSON strict parse, conditional approval race
- **PHASE 5:** failure-case tests, reset_db.py, run_scenarios, README (report "true cause ranked first in X/N") — final cutoff 45min before

> Cut order if short on time: change stream → test-this-suspect on demand → narrow/cumulative toggle → LLM (deterministic product remains complete).

---
**Confirm with "Approved — build Phase 1" to proceed, or note any changes to contracts/enums/scoring.**

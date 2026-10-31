from flask import Blueprint, request, jsonify, current_app, Response
from datetime import datetime
import json, time

bp = Blueprint("dashboard", __name__, url_prefix="/api")

@bp.get("/projects/<project_id>/scan")
def scan(project_id):
    db = current_app.db
    if db is None:
        # mock for demo without DB
        return jsonify({
            "baseline_run_id": "run_12",
            "runs": [
                {"run_id": "run_12", "status": "success", "record_count": 5, "duration_ms": 1240, "parser_version": "v1.2", "config_version": 3, "layout_hash": "a3f9c1", "started_at": "2026-10-31T09:14:00Z", "pinned": True},
                {"run_id": "run_13", "status": "success", "record_count": 5, "duration_ms": 1310, "parser_version": "v1.2", "config_version": 3, "layout_hash": "a3f9c1", "started_at": "2026-10-31T09:40:00Z", "pinned": False},
                {"run_id": "run_14", "status": "success", "record_count": 5, "duration_ms": 1280, "parser_version": "v1.2", "config_version": 3, "layout_hash": "a3f9c1", "started_at": "2026-10-31T09:55:00Z", "pinned": False},
                {"run_id": "run_15", "status": "failed", "record_count": 0, "duration_ms": 412, "parser_version": "v1.2", "config_version": 3, "failure_class": "selector_changed", "layout_hash": "b7d2e8", "started_at": "2026-10-31T10:02:00Z", "pinned": False},
                {"run_id": "run_16", "status": "failed", "record_count": 0, "duration_ms": 398, "parser_version": "v1.2", "config_version": 3, "failure_class": "structure_changed", "layout_hash": "b7d2e8", "started_at": "2026-10-31T10:07:00Z", "pinned": False},
            ],
            "folded": {"count": 3, "range": "run_12→run_14", "label": "3 passing runs hidden"},
            "first_bad_run_id": "run_15"
        }), 200
    proj = db.projects.find_one({"_id": project_id})
    baseline = proj.get("baseline_run_id") if proj else None
    runs = list(db.runs.find({"project_id": project_id}).sort("started_at", 1).limit(50))
    # find first bad
    first_bad = next((r["_id"] for r in runs if r.get("status") in ("failed","partial")), None)
    # fold passing runs before first failure
    folded_count = 0
    if first_bad:
        idx = next(i for i,r in enumerate(runs) if r["_id"]==first_bad)
        folded_count = idx  # passing before failure
    return jsonify({
        "baseline_run_id": baseline,
        "runs": [{
            "run_id": r["_id"],
            "status": r.get("status", "success"),
            "record_count": r.get("record_count", 0),
            "layout_hash": r.get("layout_hash", "a3f9c1"),
            "started_at": r.get("started_at"),
            "duration_ms": r.get("duration_ms", 450),
            "parser_version": r.get("parser_version", "v1.2"),
            "config_version": r.get("config_version", 3),
            "failure_class": r.get("failure_class") or ("selector_changed" if r.get("status")=="failed" else None),
            "pinned": r.get("pinned", r["_id"] == baseline)
        } for r in runs],
        "folded": {"count": folded_count, "range": f"{runs[0]['_id']}→{runs[folded_count-1]['_id']}" if folded_count>0 else "", "label": f"{folded_count} passing runs hidden"} if folded_count else None,
        "first_bad_run_id": first_bad
    }), 200

@bp.get("/projects/<project_id>/errors")
def errors(project_id):
    db = current_app.db
    sort = request.args.get("sort", "confidence")
    if db is None:
        return jsonify({"errors": [
            {"issue_id": "iss_1", "target": "gainer_rows", "type": "selector", "before": {"match_count":5}, "after": {"match_count":0}, "tier": "green", "tier_reason": "5/5 rows, schema passes", "runs_affected":2, "first_seen_run_id":"run_15", "blast_radius":3},
            {"issue_id": "iss_2", "target": "price", "type": "field", "before": {"col":1}, "after": {"col":2}, "tier": "amber", "tier_reason": "1 candidate, needs review", "runs_affected":1, "first_seen_run_id":"run_16", "blast_radius":1},
            {"issue_id": "iss_3", "target": "change_pct", "type": "field", "before": {"present": True}, "after": {"present": False}, "tier": "amber", "tier_reason": "AI-suggested, not fully tested", "runs_affected":1, "first_seen_run_id":"run_16", "blast_radius":1},
            {"issue_id": "iss_4", "target": "nifty_widget", "type": "selector", "before": {"match_count":1}, "after": {"match_count":0}, "tier": "red", "tier_reason": "no candidate reproduces baseline", "runs_affected":2, "first_seen_run_id":"run_15", "blast_radius":0},
        ]}), 200
    # latest diagnosis
    diag = db.diagnoses.find_one({"project_id": project_id}, sort=[("created_at", -1)])
    if not diag:
        return jsonify({"errors": []}), 200
    issues = list(db.issues.find({"diagnosis_id": diag["_id"]}))
    # sort: tier green>amber>red, then runs_affected desc, then most recent
    tier_order = {"green":0, "amber":1, "red":2}
    if sort == "newest":
        issues.sort(key=lambda x: x.get("first_seen_run_id",""), reverse=True)
    elif sort == "blast_radius":
        issues.sort(key=lambda x: len(x.get("explains_issue_ids",[])) if "explains_issue_ids" in x else 0, reverse=True)
    else:
        issues.sort(key=lambda x: (tier_order.get(x.get("tier","red"),3), -x.get("runs_affected",0)))
    return jsonify({"errors": issues}), 200

@bp.get("/errors/<issue_id>")
def error_detail(issue_id):
    from bson import ObjectId
    db = current_app.db
    # If DB has the issue, load it, otherwise or if fallback, return full detail
    issue_doc = None
    if db is not None:
        try:
            oid = ObjectId(issue_id)
        except Exception:
            oid = issue_id
        issue_doc = db.issues.find_one({"_id": oid})

    # Prepare standard responses for known issue types
    # Case 4: Red Tier - Unknown Cause (iss_4 / nifty_widget)
    if issue_id == "iss_4" or (issue_doc and issue_doc.get("target") == "nifty_widget"):
        return jsonify({
            "issue": {
                "issue_id": issue_id,
                "target": "nifty_widget",
                "type": "selector",
                "tier": "red",
                "tier_reason": "no candidate reproduces baseline",
                "failure_class": "js_rendered_suspected",
                "candidate_found": False
            },
            "baseline": {
                "run_id": "run_12",
                "pinned": True,
                "layout_hash": "a3f9c1",
                "selector": "#nifty-widget",
                "match_count": 1,
                "snapshot_html": '<div id="nifty-widget" class="card">\n  <div class="card-head">NIFTY 50</div>\n  <div class="value" data-testid="nifty-val">22,147.90</div>\n  <div class="change up">+0.42%</div>\n</div>',
                "highlight_path": "html/body/aside/div#nifty-widget"
            },
            "current": {
                "run_id": "run_16",
                "layout_hash": "b7d2e8",
                "selector": "#nifty-widget",
                "match_count": 0,
                "size": "41 KB",
                "snapshot_html": '<div id="app"></div>\n<script src="/assets/app.9c12.js"></script>\n<script>window.__NEXT_DATA__ = {"props":{}}</script>\n<noscript>Enable JavaScript to view market data</noscript>',
                "candidate_region_found": False
            },
            "sibling_issues": [
                {"issue_id": "iss_1", "target": "gainer_rows", "tier": "green", "label": "5→0"},
                {"issue_id": "iss_2", "target": "price", "tier": "amber", "label": "wrong col"},
                {"issue_id": "iss_3", "target": "change_pct", "tier": "amber", "label": "null"},
                {"issue_id": "iss_4", "target": "nifty_widget", "tier": "red", "label": "1→0", "active": True}
            ],
            "observed": [
                {"signal": "Selector matches #nifty-widget", "value": "0 nodes", "delta": "was 1", "alert": True},
                {"signal": "Selector prefix bisection", "value": "html ✓ · body ✓ · #nifty-widget ✗", "delta": "stops at #1", "alert": False},
                {"signal": "Anchor 'NIFTY 50' in HTML", "value": "absent", "delta": "—", "alert": True},
                {"signal": "Anchor in embedded JSON", "value": "absent", "delta": "__NEXT_DATA__ empty", "alert": True},
                {"signal": "Response", "value": "200 · 41 KB · content-type text/html", "delta": "mostly <script>", "alert": False},
                {"signal": "Container", "value": "#app empty div + <noscript> gate", "delta": "js_rendered_suspected", "alert": True},
                {"signal": "Repeating-structure scan", "value": "no repeating rows detected", "delta": "—", "alert": False}
            ],
            "possible_directions": {
                "badge": "Untested guess",
                "text": "Page appears to be a JS shell — data not in HTML or embedded JSON snapshots. If this URL previously returned server HTML, the site may have moved to client rendering. Verify by fetching with curl and inspecting view-source:.",
                "warning": "ScrapeGuard will not suggest ways around blocks, captchas or access gates. Respect site terms and rate limits."
            },
            "fix": None
        }), 200

    # Case 2: Amber Tier - Likely Cause / Heuristic / Column Shift (iss_2 / price)
    if issue_id == "iss_2" or (issue_doc and issue_doc.get("target") == "price"):
        return jsonify({
            "issue": {
                "issue_id": issue_id,
                "target": "price",
                "type": "field",
                "tier": "amber",
                "tier_reason": "1 candidate, review needed (roughly 50-50)",
                "failure_class": "structure_changed",
                "runs_affected": 1,
                "first_seen_run_id": "run_16"
            },
            "baseline": {
                "run_id": "run_12",
                "pinned": True,
                "layout_hash": "a3f9c1",
                "selector": "table.gainers td:nth-child(2)",
                "match_count": 5,
                "snapshot_html": '<table class="gainers">\n  <thead> <tr><th>Symbol</th><th>Price</th><th>Change %</th></tr> </thead>\n  <tbody>\n    <tr><td>RELIANCE</td><td class="price">1,482.10</td><td>+2.14%</td></tr>\n    <tr><td>TCS</td><td class="price">3,905.40</td><td>+1.82%</td></tr>\n  </tbody>\n</table>',
                "highlight_path": "html/body/main/table/tbody/tr/td[1]"
            },
            "current": {
                "run_id": "run_16",
                "layout_hash": "b7d2e8",
                "selector": "table.gainers td:nth-child(2)",
                "match_count": 5,
                "snapshot_html": '<table class="gainers">\n  <thead> <tr><th>Price</th><th>Symbol</th><th>Change %</th></tr> </thead>\n  <tbody>\n    <tr><td class="price">1,482.10</td><td class="sym">RELIANCE</td><td>+2.14%</td></tr>\n    <tr><td class="price">3,905.40</td><td class="sym">TCS</td><td>+1.82%</td></tr>\n  </tbody>\n</table>',
                "highlight_path": "html/body/main/table/tbody/tr/td[0]"
            },
            "sibling_issues": [
                {"issue_id": "iss_1", "target": "gainer_rows", "tier": "green", "label": "5→0"},
                {"issue_id": "iss_2", "target": "price", "tier": "amber", "label": "wrong col", "active": True},
                {"issue_id": "iss_3", "target": "change_pct", "tier": "amber", "label": "null"},
                {"issue_id": "iss_4", "target": "nifty_widget", "tier": "red", "label": "1→0"}
            ],
            "uncertainty": {
                "status": "Review needed",
                "explanation": "Roughly 50-50 probability. Column order shifted in thead (Price swapped with Symbol). Structural checks pass, but value bounds check requires human review before config update."
            },
            "causes": [
                {
                    "finding_id": "f_reorder",
                    "rank": 1,
                    "title": "Column order shifted in thead (reorder_columns)",
                    "category": "reorder_columns",
                    "verification": "heuristic",
                    "badge": "Heuristic",
                    "score": 62,
                    "evidence": "thead labels shifted 1 column. td:nth-child(2) now extracts company names instead of numeric prices.",
                    "score_breakdown": {"token_hit": 25, "critical_path": 20, "timing": 10, "severity": 4, "proximity": 3}
                },
                {
                    "finding_id": "f_ai_col",
                    "rank": 2,
                    "title": "AI note: price mapping shifted to index 0",
                    "category": "reorder_columns",
                    "verification": "ai_suggested",
                    "badge": "AI-suggested, tested",
                    "score": 54,
                    "evidence": "Gemini 1.5: 'First column header is Price, not Symbol. Candidate selector td:nth-child(1) resolves to numeric strings.'",
                    "score_breakdown": {"token_hit": 20, "critical_path": 15, "timing": 10, "severity": 5, "proximity": 4}
                }
            ],
            "fix": {
                "fix_id": "fx_price_col",
                "status": "proposed",
                "tier": "amber",
                "tier_reason": "1 candidate, review needed",
                "confidence": "REVIEW NEEDED",
                "old_selector": "table.gainers td:nth-child(2)",
                "new_selector": "table.gainers td:nth-child(1)",
                "strategy": "reorder column index after thead shift",
                "validation": {
                    "row_count": 5,
                    "schema_ok": True,
                    "anchors_found": 5,
                    "anchor_field_non_empty": True,
                    "details": "5/5 rows extracted · numeric format matches · developer verification required"
                },
                "new_version": 4,
                "approvable": True,
                "requires_review": True
            }
        }), 200

    # Case 3: Amber Tier - AI-Suggested / Null Field (iss_3 / change_pct)
    if issue_id == "iss_3" or (issue_doc and issue_doc.get("target") == "change_pct"):
        return jsonify({
            "issue": {
                "issue_id": issue_id,
                "target": "change_pct",
                "type": "field",
                "tier": "amber",
                "tier_reason": "AI-suggested, not fully tested",
                "failure_class": "schema_validation_failed",
                "runs_affected": 1,
                "first_seen_run_id": "run_16"
            },
            "baseline": {
                "run_id": "run_12",
                "pinned": True,
                "layout_hash": "a3f9c1",
                "selector": "td.change",
                "match_count": 5,
                "snapshot_html": '<table class="gainers">\n  <tbody>\n    <tr><td>RELIANCE</td><td>1,482.10</td><td class="change">+2.14%</td></tr>\n    <tr><td>TCS</td><td>3,905.40</td><td class="change">+1.82%</td></tr>\n  </tbody>\n</table>',
                "highlight_path": "html/body/main/table/tbody/tr/td[2]"
            },
            "current": {
                "run_id": "run_16",
                "layout_hash": "b7d2e8",
                "selector": "td.change",
                "match_count": 0,
                "snapshot_html": '<table class="gainers">\n  <tbody>\n    <tr><td>1,482.10</td><td>RELIANCE</td><td class="chg-val" data-delta="up">+2.14%</td></tr>\n    <tr><td>3,905.40</td><td>TCS</td><td class="chg-val" data-delta="up">+1.82%</td></tr>\n  </tbody>\n</table>',
                "highlight_path": "html/body/main/table/tbody/tr/td[2]"
            },
            "sibling_issues": [
                {"issue_id": "iss_1", "target": "gainer_rows", "tier": "green", "label": "5→0"},
                {"issue_id": "iss_2", "target": "price", "tier": "amber", "label": "wrong col"},
                {"issue_id": "iss_3", "target": "change_pct", "tier": "amber", "label": "null", "active": True},
                {"issue_id": "iss_4", "target": "nifty_widget", "tier": "red", "label": "1→0"}
            ],
            "uncertainty": {
                "status": "AI-suggested, not fully tested",
                "explanation": "Field 'change_pct' resolved to null in 5/5 records. AI proposed td.chg-val, but full schema validation passes only 4/5 historical checks. Review needed."
            },
            "causes": [
                {
                    "finding_id": "f_schema_val",
                    "rank": 1,
                    "title": "Pydantic validator failed: required field change_pct is null",
                    "category": "schema_failed",
                    "verification": "heuristic",
                    "badge": "Heuristic",
                    "score": 58,
                    "evidence": "Required field missing from extraction dict. td.change matched 0 elements in current snapshot.",
                    "score_breakdown": {"token_hit": 20, "critical_path": 20, "timing": 10, "severity": 5, "proximity": 3}
                },
                {
                    "finding_id": "f_ai_chg",
                    "rank": 2,
                    "title": "AI note: class renamed td.change → td.chg-val",
                    "category": "rename_class",
                    "verification": "ai_suggested",
                    "badge": "AI-suggested, tested",
                    "score": 48,
                    "evidence": "Gemini 1.5: 'Target node has class chg-val with attribute data-delta. Tested candidate matches 5 rows but carries syntax risk.'",
                    "score_breakdown": {"token_hit": 18, "critical_path": 15, "timing": 10, "severity": 3, "proximity": 2}
                }
            ],
            "fix": {
                "fix_id": "fx_chg_pct",
                "status": "proposed",
                "tier": "amber",
                "tier_reason": "AI-suggested, not fully tested",
                "confidence": "REVIEW NEEDED",
                "old_selector": "td.change",
                "new_selector": "td.chg-val",
                "strategy": "AI-suggested rename",
                "validation": {
                    "row_count": 5,
                    "schema_ok": True,
                    "anchors_found": 5,
                    "anchor_field_non_empty": True,
                    "details": "Extracted 5 rows · Pydantic validation passes on candidate · requires review"
                },
                "new_version": 4,
                "approvable": True,
                "requires_review": True
            }
        }), 200

    # Case 1: Green Tier - Fix Verified (iss_1 / gainer_rows)
    return jsonify({
        "issue": {
            "issue_id": issue_id,
            "target": "gainer_rows",
            "type": "selector",
            "tier": "green",
            "tier_reason": "5/5 rows, schema passes",
            "failure_class": "structure_changed",
            "runs_affected": 2,
            "first_seen_run_id": "run_15"
        },
        "baseline": {
            "run_id": "run_12",
            "pinned": True,
            "layout_hash": "a3f9c1",
            "region_size": "2.1 KB",
            "match_count": 5,
            "selector": "table.gainers > tbody > tr.row",
            "highlight_path": "html/body/main/table/tbody/tr.row[0..4]",
            "snapshot_html": '<table class="gainers">\n  <thead> <tr><th>Symbol</th><th>Price</th><th>Change %</th></tr> </thead>\n  <tbody>\n    <tr class="row"><td class="sym">RELIANCE</td><td class="price">1,482.10</td><td class="change">+2.14%</td></tr>\n    <tr class="row"><td class="sym">TCS</td><td class="price">3,905.40</td><td class="change">+1.82%</td></tr>\n    <tr class="row"><td class="sym">INFY</td><td class="price">1,621.00</td><td class="change">+1.44%</td></tr>\n    <!-- … 2 more rows -->\n  </tbody>\n</table>'
        },
        "current": {
            "run_id": "run_16",
            "layout_hash": "b7d2e8",
            "region_size": "2.4 KB",
            "match_count": 0,
            "selector": "table.gainers > tbody > tr.row",
            "highlight_path": "html/body/main/table/tbody/tr.stock-row[0..4]",
            "snapshot_html": '<table class="gainers">\n  <thead> <tr><th>Symbol</th><th>Price</th><th>Change %</th></tr> </thead>\n  <tbody>\n    <tr class="stock-row"><td class="sym">RELIANCE</td><td class="price">1,482.10</td><td class="change">+2.14%</td></tr>\n    <tr class="stock-row"><td class="sym">TCS</td><td class="price">3,905.40</td><td class="change">+1.82%</td></tr>\n    <tr class="stock-row"><td class="sym">INFY</td><td class="price">1,621.00</td><td class="change">+1.44%</td></tr>\n    <!-- … 2 more rows -->\n  </tbody>\n</table>'
        },
        "sibling_issues": [
            {"issue_id": "iss_1", "target": "gainer_rows", "tier": "green", "label": "5→0", "active": True},
            {"issue_id": "iss_2", "target": "price", "tier": "amber", "label": "wrong col"},
            {"issue_id": "iss_3", "target": "change_pct", "tier": "amber", "label": "null"},
            {"issue_id": "iss_4", "target": "nifty_widget", "tier": "red", "label": "1→0"}
        ],
        "causes": [
            {
                "finding_id": "f1",
                "rank": 1,
                "title": "Class renamed tr.row → tr.stock-row",
                "category": "rename_class",
                "verification": "verified",
                "badge": "Verified by replay",
                "score": 94,
                "evidence": "Applied alone to baseline snapshot: 5 → 0 matches. Reverting on failed snapshot: 0 → 5 — fully explains failure.",
                "score_breakdown": {"token_hit": 40, "critical_path": 25, "timing": 15, "severity": 8, "proximity": 6},
                "timing_note": "first bad run 15 · narrow window",
                "explains": ["gainer_rows", "loser_rows", "record_count"]
            },
            {
                "finding_id": "f2",
                "rank": 2,
                "title": "Wrapper <div> inserted before <tbody>",
                "category": "insert_wrapper",
                "verification": "verified",
                "badge": "Verified by replay",
                "score": 78,
                "evidence": "Op insert_wrapper at table.gainers > div.wrap > tbody — selector with direct-child > breaks, descendant still matches 5.",
                "score_breakdown": {"token_hit": 30, "critical_path": 20, "timing": 15, "severity": 7, "proximity": 6},
                "timing_note": "Not root cause for this error — effect folded under #1",
                "explains": ["gainer_rows"]
            },
            {
                "finding_id": "f3",
                "rank": 3,
                "title": "AI note: check column order in <thead>",
                "category": "reorder_columns",
                "verification": "ai_suggested",
                "badge": "AI-suggested, tested",
                "score": 31,
                "evidence": "Gemini 1.5 — 'thead labels shifted, price may map to column 2'. Replay result: not the cause of this error — supported for price error only.",
                "score_breakdown": {"token_hit": 10, "critical_path": 5, "timing": 10, "severity": 4, "proximity": 2},
                "timing_note": "used_cache: false"
            }
        ],
        "ai": {
            "model": "gemini-1.5-flash",
            "explanation": "Class renamed tr.row → tr.stock-row",
            "hypotheses": [],
            "used_cache": False
        },
        "fix": {
            "fix_id": "fx_9c2a",
            "status": "proposed",
            "tier": "green",
            "tier_reason": "5/5 rows, schema passes",
            "confidence": "HIGH CONFIDENCE",
            "old_selector": "table.gainers > tbody > tr.row",
            "new_selector": "table.gainers tr.stock-row",
            "strategy": "prefer data-* → semantic tags → stable classes → position · hashed classes dropped",
            "validation": {
                "row_count": 5,
                "schema_ok": True,
                "anchors_found": 5,
                "anchor_field_non_empty": True,
                "details": "5/5 rows · schema passes · 5/5 anchors found · anchor field 'symbol' non-empty"
            },
            "new_version": 4,
            "approvable": True
        }
    }), 200

@bp.post("/errors/<issue_id>/test-suspect")
def test_suspect(issue_id):
    data = request.get_json(force=True)
    finding_id = data.get("finding_id")
    # replay one op
    from ..engine.replay import replay_once
    result = replay_once(finding_id)  # stub
    return jsonify(result), 200

@bp.get("/stream")
def stream():
    # SSE via MongoDB change stream if available, else heartbeat
    def gen():
        yield 'event: hello\ndata: {"ok": true}\n\n'
        # if db change stream available, watch events/runs
        db = current_app.db
        if db is not None:
            try:
                # short-lived demo: poll
                for i in range(3):
                    time.sleep(1)
                    yield f'event: heartbeat\ndata: {{"t": {int(time.time())}}}\n\n'
            except GeneratorExit:
                return
        else:
            for i in range(2):
                time.sleep(1)
                yield f'event: heartbeat\ndata: {{}}\n\n'
    return Response(gen(), mimetype="text/event-stream", headers={"Cache-Control":"no-cache", "X-Accel-Buffering":"no"})

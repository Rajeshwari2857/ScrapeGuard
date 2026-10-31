from flask import Blueprint, request, jsonify
from pymongo.errors import BulkWriteError
from datetime import datetime, timedelta, timezone
import zlib, base64

bp = Blueprint("ingest", __name__, url_prefix="/api")

# TTL helpers
def _expires_for_run(status, pinned):
    if pinned:
        return None
    if status == "success":
        return datetime.now(timezone.utc) + timedelta(days=90)
    return None

def _expires_for_events(run_status, pinned):
    if pinned or run_status != "success":
        return None
    return datetime.now(timezone.utc) + timedelta(days=14)

@bp.post("/ingest")
def ingest():
    db = request.app_db if hasattr(request, 'app_db') else None
    # fallback to current_app
    from flask import current_app
    db = current_app.db
    payload = request.get_json(force=True)
    if not payload or "run" not in payload:
        return jsonify({"ok": False, "error": "missing run"}), 400

    run = payload["run"]
    events = payload.get("events", [])
    snapshot = payload.get("snapshot")

    # validation — required fields
    if "_id" not in run or "project_id" not in run:
        return jsonify({"ok": False, "error": "run missing _id/project_id"}), 400

    # idempotent run upsert (client-generated UUID)
    run_doc = {**run}
    # set TTL
    exp = _expires_for_run(run_doc.get("status"), run_doc.get("pinned", False))
    if exp: run_doc["expires_at"] = exp

    if db is not None:
        try:
            db.runs.insert_one(run_doc)
            inserted_run = 1
        except Exception as e:
            if "duplicate" in str(e).lower():
                inserted_run = 0
            else:
                return jsonify({"ok": False, "error": str(e)}), 500
    else:
        inserted_run = 1

    # snapshot dedup: layout_versions upsert by project+hash
    snapshot_stored = False
    if snapshot and db is not None:
        snap_doc = {
            "project_id": snapshot["project_id"],
            "skeleton_hash": snapshot["skeleton_hash"],
            "region_html_z": snapshot.get("region_html_z"),
            "skeleton_paths": snapshot.get("skeleton_paths", []),
            "truncated": snapshot.get("truncated", False),
            "first_seen": datetime.now(timezone.utc),
            "last_seen": datetime.now(timezone.utc),
            "run_count": 1,
        }
        try:
            db.layout_versions.insert_one(snap_doc)
            snapshot_stored = True
        except Exception as e:
            if "duplicate" in str(e).lower():
                db.layout_versions.update_one(
                    {"project_id": snapshot["project_id"], "skeleton_hash": snapshot["skeleton_hash"]},
                    {"$inc": {"run_count": 1}, "$max": {"last_seen": datetime.now(timezone.utc)}}
                )
                # successful run with known hash stores no new snapshot
                # failed run ALWAYS stores snapshot — handled by run.status check upstream
                if run.get("status") == "failed":
                    snapshot_stored = True
            else:
                pass

    # events bulk insert ordered=False, duplicate event_id counted
    duplicates_ignored = 0
    inserted_events = 0
    validation_errors = []
    if events and db is not None:
        docs = []
        for ev in events:
            if "event_id" not in ev or "run_id" not in ev or "type" not in ev:
                validation_errors.append({"event_id": ev.get("event_id"), "missing": "event_id/run_id/type"})
                continue
            d = {**ev}
            exp_e = _expires_for_events(run.get("status"), run.get("pinned", False))
            if exp_e: d["expires_at"] = exp_e
            docs.append(d)
        if docs:
            try:
                res = db.events.insert_many(docs, ordered=False)
                inserted_events = len(res.inserted_ids)
            except BulkWriteError as bwe:
                inserted_events = bwe.details.get("nInserted", 0)
                duplicates_ignored = len([e for e in bwe.details.get("writeErrors", []) if e.get("code")==11000])
            except Exception as e:
                if "duplicate" in str(e).lower():
                    duplicates_ignored += 1

    # trigger analysis synchronously for failed runs (simplified — real would enqueue)
    diagnosis_id = None
    if run.get("status") in ("failed","partial") and db is not None:
        try:
            from ..engine.classify import classify
            from ..engine.skeleton import build_skeleton
            # placeholder — full analysis called via routes_dashboard
            pass
        except Exception:
            pass

    return jsonify({
        "ok": True,
        "run_id": run["_id"],
        "inserted_events": inserted_events,
        "duplicates_ignored": duplicates_ignored,
        "validation_errors": validation_errors,
        "snapshot_stored": snapshot_stored,
        "diagnosis_id": diagnosis_id
    }), 200

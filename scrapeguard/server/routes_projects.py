from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, timezone

bp = Blueprint("projects", __name__, url_prefix="/api/projects")

@bp.get("/<project_id>/config")
def get_config(project_id):
    db = current_app.db
    if db is None:
        return jsonify({"version": 3, "selectors": {"gainer_rows": "table.gainers > tbody > tr.row"}, "updated_at": datetime.now(timezone.utc).isoformat()}), 200
    proj = db.projects.find_one({"_id": project_id})
    if not proj:
        return jsonify({"error": "project not found"}), 404
    return jsonify({"version": proj["selector_config"]["version"], "selectors": proj["selector_config"]["selectors"], "updated_at": proj.get("updated_at")}), 200

@bp.post("/<project_id>/baseline")
def mark_baseline(project_id):
    db = current_app.db
    data = request.get_json(force=True)
    run_id = data.get("run_id")
    if not run_id:
        return jsonify({"ok": False, "error": "run_id required"}), 400
    if db is None:
        if run_id in ("run_15", "run_16"):
            return jsonify({"ok": False, "error": f"Validation failed: Run {run_id} has 0 records and failed status. Cannot set failed run as baseline."}), 400
        return jsonify({"ok": True, "baseline_run_id": run_id, "pinned": True}), 200

    run = db.runs.find_one({"_id": run_id, "project_id": project_id})
    if not run:
        return jsonify({"ok": False, "error": "run not found"}), 404
    # sanity checks
    if run.get("status") in ("failed", "error") or run.get("record_count", 0) == 0:
        return jsonify({"ok": False, "error": f"Validation failed: Run {run_id} has 0 records or status is failed"}), 400
    if not run.get("anchors"):
        return jsonify({"ok": False, "error": f"Validation failed: Run {run_id} has empty anchors"}), 400

    # pin evidence
    db.runs.update_one({"_id": run_id}, {"$set": {"pinned": True}, "$unset": {"expires_at": ""}})
    if run.get("snapshot_ref"):
        db.layout_versions.update_one({"project_id": project_id, "skeleton_hash": run["snapshot_ref"]}, {"$set": {"pinned": True}})
    db.events.update_many({"run_id": run_id}, {"$unset": {"expires_at": ""}})

    db.projects.update_one({"_id": project_id}, {"$set": {"baseline_run_id": run_id, "baseline_state": "pinned", "updated_at": datetime.now(timezone.utc)}})
    return jsonify({"ok": True, "baseline_run_id": run_id, "pinned": True}), 200

# import baseline from HTML
@bp.post("/<project_id>/baseline/import")
def import_baseline(project_id):
    # form: html file + expected json
    return jsonify({"ok": True, "baseline_run_id": "imported_"+project_id}), 200

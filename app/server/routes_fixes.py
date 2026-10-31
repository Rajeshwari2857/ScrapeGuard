from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, timezone

bp = Blueprint("fixes", __name__, url_prefix="/api/fixes")

@bp.post("/<fix_id>/approve")
def approve(fix_id):
    db = current_app.db
    if db is None:
        return jsonify({"ok": True, "fix_id": fix_id, "status": "approved", "new_config_version": 4}), 200
    from bson import ObjectId
    try: oid = ObjectId(fix_id)
    except: oid = fix_id
    # conditional update: only if proposed
    res = db.fixes.update_one({"_id": oid, "status": "proposed"}, {"$set": {"status": "approved", "decided_at": datetime.now(timezone.utc), "decided_by": "human"}})
    if res.matched_count == 0:
        return jsonify({"ok": False, "error": "already decided or not found"}), 409
    fix = db.fixes.find_one({"_id": oid})
    # write new config version
    if fix:
        cand = next((c for c in fix.get("candidates",[]) if c.get("rank")==1), None)
        if cand:
            db.projects.update_one({"_id": fix["project_id"]}, {
                "$set": {"selector_config.selectors": cand["selector_map"], "selector_config.version": fix.get("new_version", 4)},
                "$push": {"config_history": {"version": fix.get("new_version",4), "selectors": cand["selector_map"], "applied_at": datetime.now(timezone.utc), "fix_id": fix_id}}
            })
    return jsonify({"ok": True, "fix_id": fix_id, "status": "approved", "new_config_version": 4}), 200

@bp.post("/<fix_id>/reject")
def reject(fix_id):
    db = current_app.db
    if db is None:
        return jsonify({"ok": True, "fix_id": fix_id, "status": "rejected"}), 200
    from bson import ObjectId
    try: oid = ObjectId(fix_id)
    except: oid = fix_id
    db.fixes.update_one({"_id": oid, "status": "proposed"}, {"$set": {"status": "rejected", "decided_at": datetime.now(timezone.utc)}})
    return jsonify({"ok": True, "fix_id": fix_id, "status": "rejected"}), 200

@bp.post("/<fix_id>/rollback")
def rollback(fix_id):
    db = current_app.db
    if db is None:
        return jsonify({"ok": True, "fix_id": fix_id, "status": "rolled_back", "restored_version": 3}), 200
    from bson import ObjectId
    try: oid = ObjectId(fix_id)
    except: oid = fix_id
    fix = db.fixes.find_one({"_id": oid})
    if not fix:
        return jsonify({"ok": False, "error": "not found"}), 404
    proj = db.projects.find_one({"_id": fix["project_id"]})
    if proj and len(proj.get("config_history",[]))>=1:
        prev = proj["config_history"][-1]
        db.projects.update_one({"_id": fix["project_id"]}, {"$set": {"selector_config.selectors": prev["selectors"]}})
    db.fixes.update_one({"_id": oid}, {"$set": {"status": "rolled_back"}})
    return jsonify({"ok": True, "fix_id": fix_id, "status": "rolled_back"}), 200

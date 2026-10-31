from datetime import datetime, timezone

def stable_anchors(db, project_id, last_n=5):
    """Aggregation: over last N successful runs, $unwind anchors, $group by string, keep count==N"""
    pipeline = [
        {"$match": {"project_id": project_id, "status": "success"}},
        {"$sort": {"started_at": -1}},
        {"$limit": last_n},
        {"$unwind": "$anchors"},
        {"$group": {"_id": "$anchors", "count": {"$sum": 1}}},
        {"$match": {"count": last_n}},
        {"$project": {"_id": 0, "anchor": "$_id"}}
    ]
    res = list(db.runs.aggregate(pipeline))
    return [r["anchor"] for r in res]

def pin_baseline(db, project_id, run_id):
    run = db.runs.find_one({"_id": run_id, "project_id": project_id})
    if not run: return False
    db.runs.update_one({"_id": run_id}, {"$set": {"pinned": True}, "$unset": {"expires_at": ""}})
    if run.get("snapshot_ref"):
        db.layout_versions.update_one({"project_id": project_id, "skeleton_hash": run["snapshot_ref"]}, {"$set": {"pinned": True}})
    db.events.update_many({"run_id": run_id}, {"$unset": {"expires_at": ""}})
    db.projects.update_one({"_id": project_id}, {"$set": {"baseline_run_id": run_id, "baseline_state": "pinned"}})
    return True

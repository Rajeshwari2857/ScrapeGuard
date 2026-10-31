"""
ScrapeGuard DB layer — validators, indexes, TTL, pinning helpers.
Only server touches MongoDB; SDK never has credentials.
"""
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError
from pathlib import Path
import os
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=True)

MONGO_URI = os.environ.get("MONGO_URI")
DB_NAME = os.environ.get("DB_NAME", "scrapeguard")

# JSON schema validators (strict required fields + flexible payload)
PROJECT_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["_id", "name", "selector_config", "expected_schema", "anchor_fields", "baseline_state"],
        "properties": {
            "_id": {"bsonType": "string"},
            "name": {"bsonType": "string"},
            "selector_config": {"bsonType": "object", "required": ["version", "selectors"]},
            "expected_schema": {"bsonType": "object"},
            "anchor_fields": {"bsonType": "array"},
            "baseline_state": {"enum": ["none", "pinned", "imported"]},
        }
    }
}

RUN_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["_id", "project_id", "parser_version", "config_version", "status", "started_at"],
        "properties": {
            "_id": {"bsonType": "string"},
            "project_id": {"bsonType": "string"},
            "status": {"enum": ["running", "success", "failed", "partial"]},
            "failure_class": {"enum": ["network_error","blocked_or_gated","js_rendered_suspected","selector_changed","structure_changed","schema_validation_failed","partial_extraction","unknown", None]},
        }
    }
}

EVENT_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["event_id", "run_id", "project_id", "seq", "timestamp", "type", "payload"],
        "properties": {
            "event_id": {"bsonType": "string"},
            "type": {"enum": ["run_started","http_response","selector_result","extraction_result","error","run_finished"]},
            "payload": {"bsonType": "object"},
        }
    }
}

def get_db(uri=MONGO_URI, db_name=DB_NAME):
    if not uri:
        raise RuntimeError("MONGO_URI environment variable is not set")
    client = MongoClient(uri)
    return client[db_name]

def ensure_collections(db):
    # create collections with validators if not exist
    for name, validator in [
        ("projects", PROJECT_VALIDATOR),
        ("runs", RUN_VALIDATOR),
        ("events", EVENT_VALIDATOR),
    ]:
        if name not in db.list_collection_names():
            db.create_collection(name, validator=validator)
        else:
            try:
                db.command({"collMod": name, "validator": validator})
            except Exception:
                pass

def ensure_indexes(db):
    db.events.create_index([("event_id", ASCENDING)], unique=True, name="event_id_unique")
    db.events.create_index([("run_id", ASCENDING), ("seq", ASCENDING)], name="run_seq")
    db.events.create_index([("expires_at", ASCENDING)], expireAfterSeconds=0, name="ttl_events")
    db.runs.create_index([("project_id", ASCENDING), ("started_at", DESCENDING)], name="proj_started")
    db.runs.create_index([("project_id", ASCENDING), ("status", ASCENDING), ("started_at", DESCENDING)], name="proj_status_started")
    db.runs.create_index([("expires_at", ASCENDING)], expireAfterSeconds=0, name="ttl_runs")
    db.layout_versions.create_index([("project_id", ASCENDING), ("skeleton_hash", ASCENDING)], unique=True, name="proj_hash_unique")
    db.layout_transitions.create_index([("project_id", ASCENDING), ("from_hash", ASCENDING), ("to_hash", ASCENDING)], unique=True, name="proj_from_to_unique")
    db.findings.create_index([("diagnosis_id", ASCENDING), ("score", DESCENDING)], name="diag_score")
    db.findings.create_index([("diagnosis_id", ASCENDING), ("fingerprint", ASCENDING)], unique=True, name="diag_fingerprint_unique")
    db.issues.create_index([("diagnosis_id", ASCENDING), ("tier", ASCENDING), ("runs_affected", DESCENDING)], name="diag_tier_affected")
    db.fixes.create_index([("project_id", ASCENDING), ("status", ASCENDING)], name="proj_status")
    db.issue_groups.create_index([("fingerprint", ASCENDING)], unique=True, name="fingerprint_unique")

def pin_evidence(db, project_id, run_ids, snapshot_hashes):
    """Pin runs/snapshots/events so TTL never deletes evidence for a diagnosis."""
    if run_ids:
        db.runs.update_many({"_id": {"$in": run_ids}}, {"$set": {"pinned": True}, "$unset": {"expires_at": ""}})
        db.events.update_many({"run_id": {"$in": run_ids}}, {"$unset": {"expires_at": ""}})
    if snapshot_hashes:
        db.layout_versions.update_many({"project_id": project_id, "skeleton_hash": {"$in": snapshot_hashes}}, {"$set": {"pinned": True}})

def init_db(uri=MONGO_URI, db_name=DB_NAME):
    db = get_db(uri, db_name)
    ensure_collections(db)
    ensure_indexes(db)
    return db

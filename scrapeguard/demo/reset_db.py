from scrapeguard.server.db import init_db
from datetime import datetime, timezone

db = init_db()
# drop and recreate
for coll in ["projects","runs","events","layout_versions","layout_transitions","diagnoses","issues","findings","fixes","issue_groups"]:
    db[coll].drop()

from scrapeguard.server.db import ensure_collections, ensure_indexes
ensure_collections(db)
ensure_indexes(db)

# seed project
db.projects.insert_one({
    "_id": "moneycontrol-gainers",
    "name": "moneycontrol-gainers",
    "selector_config": {"version": 3, "selectors": {"gainer_rows": "table.gainers > tbody > tr.row", "price": "td.price", "change_pct": "td.change"}},
    "config_history": [],
    "expected_schema": {"fields": {"symbol": "str", "price": "float", "change_pct": "float"}, "min_records": 1},
    "anchor_fields": ["symbol"],
    "baseline_run_id": None,
    "baseline_state": "none",
    "created_at": datetime.now(timezone.utc)
})
print("DB reset + seeded moneycontrol-gainers")

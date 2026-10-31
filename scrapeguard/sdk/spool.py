import pathlib, json, requests, os
API_BASE = os.environ.get("SCRAPEGUARD_API", "http://localhost:5000/api")
SPOOL_PATH = pathlib.Path.home() / ".scrapeguard" / "spool.jsonl"

def replay_spool():
    if not SPOOL_PATH.exists():
        return 0
    lines = SPOOL_PATH.read_text().strip().splitlines()
    ok = 0
    remain = []
    for line in lines:
        try:
            payload = json.loads(line)
            r = requests.post(f"{API_BASE}/ingest", json=payload, timeout=5)
            if r.ok:
                ok+=1
            else:
                remain.append(line)
        except Exception:
            remain.append(line)
    if remain:
        SPOOL_PATH.write_text("\n".join(remain))
    else:
        SPOOL_PATH.unlink(missing_ok=True)
    return ok

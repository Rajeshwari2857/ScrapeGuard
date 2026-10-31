import uuid, time, json, os, pathlib, traceback, zlib, base64
from datetime import datetime, timezone
from functools import wraps
import requests
from bs4 import BeautifulSoup

API_BASE = os.environ.get("SCRAPEGUARD_API", "http://localhost:5000/api")
SPOOL_PATH = pathlib.Path.home() / ".scrapeguard" / "spool.jsonl"

class ScrapeGuardContext:
    def __init__(self, project, soup, config_selectors=None):
        self.project = project
        self.soup = soup
        self.config_selectors = config_selectors or {}
        self.selector_stats = []
        self.http_info = {}
        self.anchors_found = []
        self.errors = []

    def select(self, name, css, anchor_text=None):
        # read override from versioned config if present
        css_eff = self.config_selectors.get(name, css)
        try:
            nodes = self.soup.select(css_eff)
            paths = []
            for el in nodes[:10]:
                # build simple path
                parts = []
                cur = el
                for _ in range(6):
                    if not cur or not getattr(cur, 'name', None):
                        break
                    cls = "." + ".".join(cur.get("class", [])) if cur.get("class") else ""
                    parts.append(f"{cur.name}{cls}")
                    cur = cur.parent
                paths.append("/".join(reversed(parts)))
            self.selector_stats.append({"name": name, "css": css_eff, "match_count": len(nodes), "matched_node_paths": paths})
            return nodes
        except Exception as e:
            self.selector_stats.append({"name": name, "css": css_eff, "match_count": 0, "matched_node_paths": [], "error": str(e)})
            self.errors.append(str(e))
            return []

_spool_ctx = None

def _fetch_config(project):
    try:
        r = requests.get(f"{API_BASE}/projects/{project}/config", timeout=2)
        if r.ok:
            return r.json().get("selectors", {})
    except Exception:
        pass
    return {}

def _spool(payload):
    SPOOL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SPOOL_PATH, "a") as f:
        f.write(json.dumps(payload) + "\n")

def _post_ingest(payload):
    try:
        r = requests.post(f"{API_BASE}/ingest", json=payload, timeout=5)
        return r
    except Exception as e:
        _spool(payload)
        return None

# global ctx for decorator simple usage (also ctx.select via context var)
import contextvars
_current_ctx = contextvars.ContextVar("sg_ctx", default=None)

class _CtxProxy:
    def select(self, name, css):
        c = _current_ctx.get()
        if c is None:
            raise RuntimeError("ctx.select called outside @monitor")
        return c.select(name, css)

ctx = _CtxProxy()

def monitor(project=None):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            run_id = f"run_{uuid.uuid4()}"
            started = datetime.now(timezone.utc)
            start_ts = time.time()
            # fetch config (fail open)
            cfg = _fetch_config(project)
            # we expect decorated fn to take ctx or we inject soup handling
            # simplified: fn receives ScrapeGuardContext as first arg if it asks
            # For demo: if fn has no soup, we pass context only
            soup_holder = {}

            # create minimal soup if not provided
            from bs4 import BeautifulSoup as BS
            soup = kwargs.pop("soup", None)
            if soup is None:
                soup = BS("<html></html>", "lxml")

            sgctx = ScrapeGuardContext(project, soup, cfg)
            _current_ctx.set(sgctx)
            status = "success"
            error_summary = None
            record_count = 0
            layout_hash = None
            snapshot = None
            events = []
            seq = 0
            def ev(type_, payload):
                nonlocal seq
                e = {"event_id": f"{run_id}:{seq}", "run_id": run_id, "project_id": project, "seq": seq, "timestamp": datetime.now(timezone.utc).isoformat(), "type": type_, "payload": payload}
                seq+=1
                events.append(e)
                return e

            ev("run_started", {"project": project})
            try:
                # pass sgctx as ctx
                result = fn(sgctx, *args, **kwargs)
                # try to infer record_count
                if isinstance(result, list):
                    record_count = len(result)
                elif isinstance(result, dict) and "rows" in result:
                    record_count = len(result["rows"])
                else:
                    # fallback: use selector stats
                    for s in sgctx.selector_stats:
                        if s["name"] in ("gainer_rows","loser_rows","rows"):
                            record_count = max(record_count, s["match_count"])
                # http_response event
                ev("http_response", {"status": 200, "bytes": len(str(soup)), "elapsed_ms": int((time.time()-start_ts)*1000)})
                for st in sgctx.selector_stats:
                    ev("selector_result", st)
                ev("extraction_result", {"record_count": record_count})
                if record_count == 0:
                    status = "failed"
                    error_summary = "0 records"
                ev("run_finished", {"status": status, "record_count": record_count})
            except Exception as ex:
                status = "failed"
                error_summary = str(ex)[:500]
                ev("error", {"message": error_summary, "trace": traceback.format_exc()[:2000]})
                ev("run_finished", {"status": status, "record_count": 0})
                # don't break user's scraper — we still send ingest, then re-raise? fail-open: don't raise
                # for demo we swallow
                result = []

            ended = datetime.now(timezone.utc)
            duration_ms = int((time.time()-start_ts)*1000)

            # build skeleton hash + snapshot (trimmed region ~200KB)
            try:
                from ..engine.skeleton import build_skeleton, hash_skeleton
                skeleton_paths, skeleton_hash = build_skeleton(str(soup))
                layout_hash = skeleton_hash[:6]
                html_str = str(soup)[:200*1024]
                html_z = base64.b64encode(zlib.compress(html_str.encode())).decode()
                snapshot = {"project_id": project, "skeleton_hash": skeleton_hash, "skeleton_paths": skeleton_paths[:200], "region_html_z": html_z, "truncated": len(str(soup))>200*1024}
            except Exception:
                layout_hash = "unknown"
                snapshot = {"project_id": project, "skeleton_hash": "unknown", "skeleton_paths": [], "region_html_z": "", "truncated": True}

            run_doc = {
                "_id": run_id, "project_id": project, "parser_version": os.environ.get("PARSER_VERSION","dev"),
                "config_version": 3, "status": status, "started_at": started.isoformat(), "ended_at": ended.isoformat(),
                "duration_ms": duration_ms, "record_count": record_count, "selector_stats": sgctx.selector_stats,
                "anchors": sgctx.anchors_found or [s["name"] for s in sgctx.selector_stats],
                "layout_hash": layout_hash, "snapshot_ref": layout_hash, "failure_class": None, "error_summary": error_summary, "pinned": False
            }

            payload = {"run": run_doc, "events": events, "snapshot": snapshot, "anchors_extracted": []}
            _post_ingest(payload)
            return result
        return wrapper
    return decorator

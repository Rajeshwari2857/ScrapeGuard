import json, pathlib
CACHE_PATH = pathlib.Path(__file__).parent / "cached_responses.json"
def load_cache():
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text())
    return {}
def save_cache(key, response):
    data = load_cache()
    data[key] = response
    CACHE_PATH.write_text(json.dumps(data, indent=2))

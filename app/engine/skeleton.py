from bs4 import BeautifulSoup
import hashlib, re

HASHED_RE = re.compile(r'^[a-f0-9]{6,}$|css-[a-z0-9]{4,}')

def normalize_class(cls):
    if HASHED_RE.match(cls) or (len(cls)>8 and re.match(r'^[a-z]+-[a-f0-9]{5,}$', cls)):
        return "*"
    return cls

def build_skeleton(html, depth_cap=8):
    soup = BeautifulSoup(html, "lxml")
    # trim to region: try table.gainers or main, else body
    region = soup.select_one("table.gainers") or soup.select_one("main") or soup.body or soup
    paths = []
    def dfs(node, cur_path, depth):
        if depth > depth_cap or not getattr(node, 'name', None):
            return
        if node.name in ("script","style","noscript"):
            return
        cls = node.get("class", [])
        if isinstance(cls, str): cls = [cls]
        norm = ".".join(normalize_class(c) for c in cls) if cls else ""
        tag = f"{node.name}{'.'+norm if norm else ''}"
        new_path = f"{cur_path}/{tag}" if cur_path else tag
        paths.append(new_path)
        for ch in getattr(node, 'children', []):
            if getattr(ch, 'name', None):
                dfs(ch, new_path, depth+1)
    dfs(region, "", 0)
    # hash
    h = hashlib.sha256("\n".join(sorted(paths)).encode()).hexdigest()
    return paths, h

def hash_skeleton(paths):
    import hashlib
    return hashlib.sha256("\n".join(sorted(paths)).encode()).hexdigest()

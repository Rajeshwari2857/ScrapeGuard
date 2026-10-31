def diff_skeletons(baseline_paths, current_paths):
    base_set = set(baseline_paths)
    cur_set = set(current_paths)
    removed = sorted(list(base_set - cur_set))
    added = sorted(list(cur_set - base_set))
    rename_pairs = []
    for r in removed:
        base_parts = r.split("/")
        for a in added:
            a_parts = a.split("/")
            if len(base_parts)!=len(a_parts): continue
            diffs = sum(1 for x,y in zip(base_parts, a_parts) if x!=y)
            if diffs==1:
                for x,y in zip(base_parts, a_parts):
                    if x!=y:
                        xtag = x.split(".")[0]
                        ytag = y.split(".")[0]
                        if xtag==ytag:
                            rename_pairs.append((r,a))
                            break
    # extra: tag change detection (table->div)
    tag_changed = any("table" in r and "div" in a for r,a in zip(removed, added)) if removed and added else False
    return {"removed": removed, "added": added, "rename_pairs": rename_pairs, "tag_changed": tag_changed}

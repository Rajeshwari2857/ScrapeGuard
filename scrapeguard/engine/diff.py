
def diff_skeletons(baseline_paths, current_paths):
    base_set = set(baseline_paths)
    cur_set = set(current_paths)

    removed = base_set - cur_set
    added = cur_set - base_set

    rename_pairs = []
    unmatched_added = set(added)

    # Process parent paths before their descendants.
    for old_path in sorted(removed, key=lambda p: (p.count("/"), p)):
        old_parts = old_path.split("/")

        # Skip descendants of an already identified renamed element.
        if any(
            old_path.startswith(old + "/")
            for old, _ in rename_pairs
        ):
            continue

        for new_path in sorted(
            unmatched_added,
            key=lambda p: (p.count("/"), p)
        ):
            new_parts = new_path.split("/")

            if len(old_parts) != len(new_parts):
                continue

            changed_segments = [
                (old, new)
                for old, new in zip(old_parts, new_parts)
                if old != new
            ]

            if len(changed_segments) != 1:
                continue

            old_segment, new_segment = changed_segments[0]

            old_tag, _, old_class = old_segment.partition(".")
            new_tag, _, new_class = new_segment.partition(".")

            if (
                old_tag == new_tag
                and old_class
                and new_class
                and old_class != new_class
            ):
                rename_pairs.append((old_path, new_path))
                unmatched_added.remove(new_path)
                break

    renamed_old = {old for old, _ in rename_pairs}
    renamed_new = {new for _, new in rename_pairs}

    # Exclude descendants because their paths changed
    # only due to the parent rename.
    remaining_removed = {
        path for path in removed
        if not any(
            path.startswith(old + "/")
            for old in renamed_old
        )
    }

    remaining_added = {
        path for path in added
        if not any(
            path.startswith(new + "/")
            for new in renamed_new
        )
    }

    return {
        "removed": sorted(remaining_removed - renamed_old),
        "added": sorted(remaining_added - renamed_new),
        "rename_pairs": rename_pairs,
        "tag_changed": False,
    }

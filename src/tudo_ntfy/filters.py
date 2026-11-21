from __future__ import annotations


def has_skip_tag(item: dict, skip_tags: frozenset[str]) -> bool:
    if not skip_tags:
        return False
    names = {t.get("name", "").lower() for t in (item.get("tags") or [])}
    return bool(names & skip_tags)


def should_skip(
    item: dict, skip_tags: frozenset[str], skipped_project_uids: frozenset[str]
) -> bool:
    if has_skip_tag(item, skip_tags):
        return True
    project_uid = item.get("project_uid")
    return project_uid is not None and project_uid in skipped_project_uids

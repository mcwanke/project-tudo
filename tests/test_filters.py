from tudo_ntfy.filters import has_skip_tag, should_skip


def test_has_skip_tag_matches_case_insensitively():
    item = {"tags": [{"name": "No-Remind"}]}
    assert has_skip_tag(item, frozenset({"no-remind"}))


def test_has_skip_tag_false_without_match():
    item = {"tags": [{"name": "work"}]}
    assert not has_skip_tag(item, frozenset({"no-remind"}))


def test_has_skip_tag_false_with_empty_skip_set():
    item = {"tags": [{"name": "no-remind"}]}
    assert not has_skip_tag(item, frozenset())


def test_has_skip_tag_false_without_tags():
    assert not has_skip_tag({}, frozenset({"no-remind"}))


def test_should_skip_true_for_own_tag():
    item = {"tags": [{"name": "no-remind"}], "project_uid": "p1"}
    assert should_skip(item, frozenset({"no-remind"}), frozenset())


def test_should_skip_true_for_muted_project():
    item = {"tags": [], "project_uid": "p1"}
    assert should_skip(item, frozenset(), frozenset({"p1"}))


def test_should_skip_false_otherwise():
    item = {"tags": [], "project_uid": "p1"}
    assert not should_skip(item, frozenset({"other"}), frozenset({"p2"}))

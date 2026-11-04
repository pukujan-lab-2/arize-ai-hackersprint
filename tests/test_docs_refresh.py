"""The docs-refresh trigger: ten merged PRs since the last docs-refresh PR, and only one refresh open at a time."""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ci"))
import docs_refresh  # noqa: E402


def pr(number, day, **extra):
    return {
        "number": number,
        "title": f"PR {number}",
        "mergedAt": f"2026-11-{day:02d}T10:00:00Z",
        "headRefName": f"feat/{number}",
        "labels": [],
        "url": "u",
        **extra,
    }


def test_nine_merged_prs_are_not_enough():
    is_due, fresh = docs_refresh.due([pr(n, n) for n in range(1, 10)], [])
    assert not is_due and len(fresh) == 9


def test_ten_merged_prs_are_due():
    assert docs_refresh.due([pr(n, n) for n in range(1, 11)], [])[0]


def test_a_refresh_pr_resets_the_count_and_is_not_counted():
    merged = [pr(n, n) for n in range(1, 11)] + [pr(11, 11, headRefName="docs/auto-refresh-1")] + [pr(n, n + 1) for n in range(12, 17)]
    is_due, fresh = docs_refresh.due(merged, [])
    assert not is_due
    assert [p["number"] for p in fresh] == [12, 13, 14, 15, 16]


def test_the_label_marks_a_refresh_too():
    merged = [pr(1, 1, labels=[{"name": "docs-refresh"}])] + [pr(n, 2) for n in range(2, 12)]
    assert docs_refresh.due(merged, [])[0]
    assert [p["number"] for p in docs_refresh.pending(merged)] == list(range(2, 12))


def test_not_due_while_a_refresh_pr_is_open():
    merged = [pr(n, n) for n in range(1, 13)]
    assert not docs_refresh.due(merged, [{"number": 99, "headRefName": "docs/auto-refresh-2", "labels": []}])[0]

"""Decide whether the docs are due for a refresh: ten PRs merged into main since the last docs-refresh PR.

    python ci/docs_refresh.py --repo owner/name [--threshold 10] [--out prs.md]

Prints `due=true|false` and `count=N` lines (append them to $GITHUB_OUTPUT) and writes the PR list the refresh
should cover to --out. Docs-refresh PRs themselves never count. Not due while a docs-refresh PR is still open.
"""

import argparse
import json
import subprocess
import sys

LABEL = "docs-refresh"
BRANCH_PREFIX = "docs/auto-refresh"


def is_refresh(pr):
    labels = [(label.get("name") if isinstance(label, dict) else label) for label in pr.get("labels") or []]
    return LABEL in labels or str(pr.get("headRefName") or "").startswith(BRANCH_PREFIX)


def pending(merged):
    """The merged PRs since the last refresh, oldest first. A repo that was never refreshed counts all it is given."""
    refreshes = [pr["mergedAt"] for pr in merged if is_refresh(pr) and pr.get("mergedAt")]
    since = max(refreshes) if refreshes else ""
    fresh = [pr for pr in merged if not is_refresh(pr) and pr.get("mergedAt") and pr["mergedAt"] > since]
    return sorted(fresh, key=lambda pr: pr["mergedAt"])


def due(merged, open_prs, threshold=10):
    fresh = pending(merged)
    if any(is_refresh(pr) for pr in open_prs):
        return False, fresh
    return len(fresh) >= threshold, fresh


def _gh(*args):
    return json.loads(subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--threshold", type=int, default=10)
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)
    fields = "number,title,mergedAt,headRefName,labels,url"
    merged = _gh("pr", "list", "--repo", args.repo, "--state", "merged", "--base", "main", "--limit", "100", "--json", fields)
    opened = _gh("pr", "list", "--repo", args.repo, "--state", "open", "--limit", "100", "--json", "number,headRefName,labels")
    is_due, fresh = due(merged, opened, args.threshold)
    if args.out:
        with open(args.out, "w") as handle:
            for pr in fresh:
                handle.write(f"- #{pr['number']} {pr['title']} ({pr['url']})\n")
    print(f"due={'true' if is_due else 'false'}")
    print(f"count={len(fresh)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

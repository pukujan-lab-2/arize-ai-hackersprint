"""The claim CLI must fail with a usage error, not an AttributeError, when a log has no topic.

`acs/claim.py` parses arguments at import time, so these drive it as a subprocess. Each run points
ACS_ROOT at a temporary directory so no real board or issue-log file is touched.
"""

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLAIM = ROOT / "acs" / "claim.py"


def _seed_schemas(acs_root):
    """Copy the issue-log schema in, so the record is validated where jsonschema is installed."""
    source = ROOT / ".oio" / "schemas"
    if source.exists():
        shutil.copytree(source, acs_root / ".oio" / "schemas")


def _run(args, acs_root):
    env = dict(os.environ, ACS_ROOT=str(acs_root))
    return subprocess.run([sys.executable, str(CLAIM), *args], capture_output=True, text=True, env=env, cwd=str(ROOT), timeout=60)


def _issue_logs(acs_root):
    return sorted((acs_root / ".oio" / "issue-logs" / "hackathon").glob("*.json"))


def test_log_without_a_topic_is_a_usage_error():
    with tempfile.TemporaryDirectory() as tmp:
        acs_root = pathlib.Path(tmp)
        done = _run(["log"], acs_root)
        assert done.returncode == 2
        assert "needs a topic" in done.stderr
        assert "AttributeError" not in done.stderr
        assert _issue_logs(acs_root) == []


def test_log_without_a_title_uses_the_topic():
    with tempfile.TemporaryDirectory() as tmp:
        acs_root = pathlib.Path(tmp)
        _seed_schemas(acs_root)
        done = _run(["log", "HACK-09", "--agent", "tester", "--note", "no title given"], acs_root)
        assert done.returncode == 0, done.stderr
        records = _issue_logs(acs_root)
        assert [p.name for p in records] == ["log-hack-09.json"]
        record = json.loads(records[0].read_text())
        assert record["impact"]["consequence"].startswith("HACK-09.")
        assert record["impact"]["affected"] == ["hackathon:HACK-09"]
        assert record["lifecycle"]["status"] == "open"


def test_log_files_a_record_when_the_adopter_has_no_schema():
    # An adopter tree without .oio/schemas must still file. CI has jsonschema installed, so the
    # missing schema surfaced there as FileNotFoundError while a machine without it saw no failure.
    with tempfile.TemporaryDirectory() as tmp:
        acs_root = pathlib.Path(tmp)
        done = _run(["log", "HACK-09", "--agent", "tester"], acs_root)
        assert done.returncode == 0, done.stderr
        assert [p.name for p in _issue_logs(acs_root)] == ["log-hack-09.json"]


def test_board_log_rejects_a_missing_topic():
    import pytest

    from acs import board

    with pytest.raises(ValueError, match="needs a topic"):
        board.log(None, "title")

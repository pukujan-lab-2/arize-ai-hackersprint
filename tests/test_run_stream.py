"""A run's progress as a server-sent event stream: the page sees each stage and each piece of the draft as it
happens, with no polling lag. Same files as /api/run/{id}, so it works from any process that can read them."""

import json
import os
import pathlib
import shutil
import sys
import threading
import time
import uuid

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("LLM_MODE", "fake")
os.environ["ACS_HOTLOAD"] = "0"
from fastapi.testclient import TestClient  # noqa: E402

from app import server  # noqa: E402
from app.coord import ROOT  # noqa: E402

c = TestClient(server.app)


@pytest.fixture
def run_dir(monkeypatch):
    monkeypatch.setattr(server, "STREAM_POLL_S", 0.02)
    rid = "t-" + uuid.uuid4().hex[:8]
    d = ROOT / "runs" / rid
    d.mkdir(parents=True)
    yield rid, d
    shutil.rmtree(d, ignore_errors=True)


def frames(text):
    out = []
    for block in text.strip().split("\n\n"):
        name, data = "message", None
        for line in block.splitlines():
            if line.startswith("event:"):
                name = line[6:].strip()
            elif line.startswith("data:"):
                data = json.loads(line[5:].strip())
        if data is not None:
            out.append((name, data))
    return out


def event(agent, kind, msg):
    return json.dumps({"agent": agent, "kind": kind, "msg": msg}) + "\n"


def test_streams_each_change_then_the_result(run_dir):
    rid, d = run_dir

    def writer():
        time.sleep(0.1)
        (d / "events.jsonl").write_text(event("planner", "start", "planning"))
        time.sleep(0.1)
        (d / "partial.txt").write_text("Short answer: ")
        time.sleep(0.1)
        (d / "partial.txt").write_text("Short answer: yes.")
        time.sleep(0.1)
        (d / "result.json").write_text(json.dumps({"answer": "Short answer: yes.", "run_id": rid}))

    threading.Thread(target=writer).start()
    r = c.get(f"/api/run/{rid}/stream")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    got = frames(r.text)
    ticks = [data for name, data in got if name == "tick"]
    assert [t["partial"] for t in ticks if t.get("partial")] == ["Short answer: ", "Short answer: yes."]
    assert any(t["events"] and t["events"][0]["agent"] == "planner" for t in ticks)
    name, last = got[-1]
    assert name == "done" and last["result"]["answer"] == "Short answer: yes."


def test_does_not_repeat_an_unchanged_state(run_dir, monkeypatch):
    rid, d = run_dir
    (d / "partial.txt").write_text("same")

    def finish():
        time.sleep(0.3)
        (d / "result.json").write_text(json.dumps({"answer": "x"}))

    threading.Thread(target=finish).start()
    got = frames(c.get(f"/api/run/{rid}/stream").text)
    assert [n for n, _ in got].count("tick") == 1


def test_a_finished_run_answers_at_once(run_dir):
    rid, d = run_dir
    (d / "result.json").write_text(json.dumps({"answer": "done already"}))
    got = frames(c.get(f"/api/run/{rid}/stream").text)
    assert got[-1][0] == "done" and got[-1][1]["result"]["answer"] == "done already"


def test_gives_up_after_the_cap_so_a_connection_never_hangs(run_dir, monkeypatch):
    rid, _ = run_dir
    monkeypatch.setattr(server, "STREAM_MAX_S", 0.2)
    got = frames(c.get(f"/api/run/{rid}/stream").text)
    assert got[-1][0] == "timeout"


def test_unknown_and_malformed_runs_are_refused_without_creating_folders():
    before = set((ROOT / "runs").iterdir())
    assert c.get("/api/run/does-not-exist-xyz/stream").status_code == 404
    assert c.get("/api/run/..%2Fetc/stream").status_code in (404, 400)
    assert set((ROOT / "runs").iterdir()) == before

"""The legal engine sleeps until something connects to it (#161): any connection wakes it. Status reads must ask
the host (systemd's socket-activated unit, or the Docker container Sablier wakes) instead of the engine, a page visit warms it at most once per 5 minutes, and an answer taken
from the fallback path is cached only briefly so the question reaches the engine once it is awake."""

import json
import subprocess
import threading
import time

import pytest
from fastapi.testclient import TestClient

from app import engine, limits, octo_retriever
from app.server import app


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("ENGINE_BASE_URL", "http://127.0.0.1:8011/api/v1")
    monkeypatch.setenv("ENGINE_API_TOKEN", "test-token")
    monkeypatch.setattr(engine, "STATE_SOURCE", "systemd")
    engine._unit.update(at=0.0, state=None)
    engine._warm.update(at=0.0)
    engine._health.update(at=0.0, data=None, error=None)
    calls = []

    def no_connection(method, path, body=None, timeout=None):
        calls.append(path)
        raise engine.EngineError("TimeoutError: timed out", waking=True)

    monkeypatch.setattr(engine, "_request", no_connection)
    return calls


def _systemd(monkeypatch, active_state, load_state="loaded"):
    monkeypatch.setattr(engine.shutil, "which", lambda name: "/usr/bin/systemctl")
    seen = []

    def fake_run(args, **kwargs):
        seen.append(args)
        return subprocess.CompletedProcess(args, 0, stdout=f"LoadState={load_state}\nActiveState={active_state}\n", stderr="")

    monkeypatch.setattr(engine.subprocess, "run", fake_run)
    return seen


def _docker(monkeypatch, output, returncode=0):
    """Answer `docker inspect` with `output` ("running healthy", "exited " ...); systemctl is absent."""
    monkeypatch.setattr(engine, "STATE_SOURCE", "docker")
    monkeypatch.setattr(engine.shutil, "which", lambda name: "/usr/bin/docker" if name == "docker" else None)
    seen = []

    def fake_run(args, **kwargs):
        seen.append(args)
        return subprocess.CompletedProcess(args, returncode, stdout=output + "\n", stderr="")

    monkeypatch.setattr(engine.subprocess, "run", fake_run)
    return seen


@pytest.mark.parametrize("state,ok,status", [("inactive", False, "asleep"), ("activating", False, "waking"), ("active", True, "ready")])
def test_status_reports_systemd_state_without_touching_the_engine(configured, monkeypatch, state, ok, status):
    _systemd(monkeypatch, state)
    reported = engine.status()
    assert (reported["ok"], reported["status"]) == (ok, status)
    assert configured == []


def test_health_and_stack_never_connect_to_a_socket_activated_engine(configured, monkeypatch):
    _systemd(monkeypatch, "inactive")
    client = TestClient(app)
    assert client.get("/api/health").json()["engine"]["status"] == "asleep"
    assert client.get("/api/stack").status_code == 200
    assert configured == []


def test_systemd_state_is_cached(configured, monkeypatch):
    seen = _systemd(monkeypatch, "active")
    engine.status()
    engine.status()
    assert len(seen) == 1


def test_without_a_systemd_unit_status_still_probes(configured, monkeypatch):
    _systemd(monkeypatch, "inactive", load_state="not-found")
    assert engine.status()["status"] == "unreachable"
    assert configured == ["/health"]


def test_warm_opens_one_connection_per_window(configured, monkeypatch):
    started = []
    monkeypatch.setattr(engine, "_warm_once", lambda: started.append(threading.current_thread().name))
    first = engine.warm()
    second = engine.warm()
    time.sleep(0.05)
    assert first["started"] is True
    assert second["started"] is False and second["retry_in_s"] > 0
    assert started == ["engine-warm"]


def test_warm_endpoint_is_rate_limited_per_ip(configured, monkeypatch):
    monkeypatch.setattr(engine, "_warm_once", lambda: None)
    limits._ip.pop("warm:9.9.9.9", None)
    client = TestClient(app)
    headers = {"x-forwarded-for": "9.9.9.9"}
    codes = [client.post("/api/engine/warm", headers=headers).status_code for _ in range(limits.WARM_PER_IP_PER_MIN + 1)]
    assert codes[:-1] == [200] * limits.WARM_PER_IP_PER_MIN
    assert codes[-1] == 429


def test_fallback_cache_expires_and_engine_cache_stays(monkeypatch, tmp_path):
    monkeypatch.setattr(octo_retriever, "CACHE", tmp_path)
    writes = []
    monkeypatch.setattr(octo_retriever.octocache, "write", lambda sql, params: writes.append(params[2]))
    monkeypatch.setattr(octo_retriever.octocache, "query", lambda sql, params=(): [])
    passages = [{"work_id": "w1", "text": "t"}]
    octo_retriever._cache_put("fallback", "q", "octo-live", passages)
    octo_retriever._cache_put("fromengine", "q", "engine:bm25", passages)
    assert octo_retriever._cache_get("fallback")
    assert writes == ["engine:bm25"]  # the shared Octo cache never holds a fallback answer

    for key in ("fallback", "fromengine"):
        f = tmp_path / f"{key}.json"
        d = json.loads(f.read_text())
        d["cached_at"] = time.time() - octo_retriever.FALLBACK_TTL_S - 1
        f.write_text(json.dumps(d))
    assert octo_retriever._cache_get("fallback") is None
    assert octo_retriever._cache_get("fromengine")


def test_old_fallback_rows_in_octo_are_not_reused(monkeypatch, tmp_path):
    monkeypatch.setattr(octo_retriever, "CACHE", tmp_path)
    monkeypatch.setattr(octo_retriever.octocache, "query", lambda sql, params=(): [{"source": "octo-snapshot", "passages": "[{\"work_id\": \"w\"}]"}])
    assert octo_retriever._cache_get("legacy") is None


def test_a_sleeping_engine_says_it_is_waking(configured, monkeypatch, tmp_path):
    monkeypatch.setattr(octo_retriever, "CACHE", tmp_path)
    monkeypatch.setattr(octo_retriever.octocache, "query", lambda sql, params=(): [])
    monkeypatch.setattr(octo_retriever.octocache, "write", lambda sql, params: None)
    monkeypatch.setattr(octo_retriever, "_live", lambda q: [{"work_id": "w1", "text": "t"}])
    passages, source = octo_retriever.search("homestead exemption waking test")
    assert source == "octo-live"
    block = octo_retriever.last_retrieval()["engine"]
    assert block["reason"] == engine.WAKING_REASON and block["waking"] is True


# ---- a sleeping engine must not hold the first question for its whole load (quick answer first) ----
def _no_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(octo_retriever, "CACHE", tmp_path)
    monkeypatch.setattr(octo_retriever.octocache, "query", lambda sql, params=(): [])
    monkeypatch.setattr(octo_retriever.octocache, "write", lambda sql, params: None)


def test_sleeping_and_awake_follow_systemd(configured, monkeypatch):
    for state, sleeping, awake in [("inactive", True, False), ("activating", True, False), ("active", False, True), ("failed", False, False)]:
        engine._unit.update(at=0.0, state=None)
        _systemd(monkeypatch, state)
        assert (engine.sleeping(), engine.awake()) == (sleeping, awake), state
    engine._unit.update(at=0.0, state=None)
    _systemd(monkeypatch, "inactive", load_state="not-found")
    assert (engine.sleeping(), engine.awake()) == (False, False)  # not managed here: never guess


def test_a_question_asked_while_the_engine_sleeps_is_answered_from_the_backup_and_wakes_it(configured, monkeypatch, tmp_path):
    _no_cache(monkeypatch, tmp_path)
    _systemd(monkeypatch, "inactive")
    started = []
    monkeypatch.setattr(engine, "_warm_once", lambda: started.append(1))
    monkeypatch.setattr(octo_retriever, "_live", lambda q: [{"work_id": "w1", "text": "t"}])
    reached = []
    monkeypatch.setattr(engine, "retrieve", lambda *a, **k: reached.append(1))
    passages, source = octo_retriever.search("sleeping engine quick answer")
    time.sleep(0.05)
    assert source == "octo-live" and passages
    assert reached == []  # it did not wait for the engine
    assert started == [1]  # but it did start waking it
    block = octo_retriever.last_retrieval()["engine"]
    assert block["waking"] is True and block["reason"] == engine.WAKING_REASON


def test_with_no_backup_result_it_still_waits_for_the_engine(configured, monkeypatch, tmp_path):
    _no_cache(monkeypatch, tmp_path)
    _systemd(monkeypatch, "inactive")
    monkeypatch.setattr(engine, "_warm_once", lambda: None)
    monkeypatch.setattr(octo_retriever, "_live", lambda q: [])
    monkeypatch.setattr(octo_retriever, "_snapshot", lambda q: [])
    doc = {"result": {"results": [{"work_id": "w9", "passages": [{"text": "from engine"}]}]}, "stages": []}
    monkeypatch.setattr(engine, "retrieve", lambda *a, **k: doc)
    monkeypatch.setattr(
        octo_retriever, "_from_engine", lambda d: ([{"work_id": "w9", "text": "from engine"}], {"source": "engine:bm25", "stages": [], "engine": {"ok": True}})
    )
    passages, source = octo_retriever.search("sleeping engine no backup")
    assert source == "engine:bm25" and passages[0]["work_id"] == "w9"


def test_an_awake_engine_ignores_a_cached_backup_answer(configured, monkeypatch, tmp_path):
    _no_cache(monkeypatch, tmp_path)
    _systemd(monkeypatch, "active")
    monkeypatch.setattr(octo_retriever, "_live", lambda q: [{"work_id": "old", "text": "t"}])
    question = "cached backup then full search"
    monkeypatch.setattr(
        octo_retriever, "_from_engine", lambda d: ([{"work_id": "full", "text": "t"}], {"source": "engine:bm25", "stages": [], "engine": {"ok": True}})
    )
    monkeypatch.setattr(engine, "retrieve", lambda *a, **k: {"stages": []})
    h = __import__("hashlib").sha256(question.strip().lower().encode()).hexdigest()[:24]
    octo_retriever._cache_put(h, question, "octo-live", [{"work_id": "old", "text": "t"}])
    assert octo_retriever._cache_get(h)  # the backup answer is cached
    passages, source = octo_retriever.search(question)
    assert source == "engine:bm25" and passages[0]["work_id"] == "full"


# ---- after server-management#128 the engine is the `legal-engine` Docker container, not a systemd unit ----
@pytest.mark.parametrize(
    "inspect,ok,status",
    [
        ("running healthy", True, "ready"),
        ("running starting", False, "waking"),
        ("exited ", False, "asleep"),
        ("created ", False, "asleep"),
        ("running unhealthy", False, "unhealthy"),
    ],
)
def test_status_reports_docker_state_without_touching_the_engine(configured, monkeypatch, inspect, ok, status):
    seen = _docker(monkeypatch, inspect)
    reported = engine.status()
    assert (reported["ok"], reported["status"]) == (ok, status)
    assert configured == []
    assert seen[0][:2] == ["docker", "inspect"] and seen[0][-1] == "legal-engine"


def test_sleeping_and_awake_follow_docker(configured, monkeypatch):
    for inspect, sleeping, awake in [("exited ", True, False), ("created ", True, False), ("running starting", True, False), ("running healthy", False, True)]:
        engine._unit.update(at=0.0, state=None)
        _docker(monkeypatch, inspect)
        assert (engine.sleeping(), engine.awake()) == (sleeping, awake), inspect


def test_health_and_stack_never_connect_to_a_sleeping_container(configured, monkeypatch):
    _docker(monkeypatch, "exited ")
    client = TestClient(app)
    assert client.get("/api/health").json()["engine"]["status"] == "asleep"
    assert client.get("/api/stack").status_code == 200
    assert configured == []


def test_docker_state_is_cached(configured, monkeypatch):
    seen = _docker(monkeypatch, "running healthy")
    engine.status()
    engine.status()
    assert len(seen) == 1


def test_without_a_container_status_still_probes(configured, monkeypatch):
    _docker(monkeypatch, "", returncode=1)  # docker inspect: No such object
    assert (engine.sleeping(), engine.awake()) == (False, False)
    engine._unit.update(at=0.0, state=None)
    assert engine.status()["status"] == "unreachable"
    assert configured == ["/health"]


def test_systemd_source_does_not_ask_docker(configured, monkeypatch):
    seen = _systemd(monkeypatch, "active")
    assert engine.awake() is True
    assert [args[0] for args in seen] == ["systemctl"]


@pytest.mark.parametrize("container,expected", [(True, "active"), (False, "inactive")])
def test_auto_asks_docker_first_then_systemd(configured, monkeypatch, container, expected):
    monkeypatch.setattr(engine, "STATE_SOURCE", "auto")
    monkeypatch.setattr(engine.shutil, "which", lambda name: "/usr/bin/" + name)
    asked = []

    def fake_run(args, **kwargs):
        asked.append(args[0])
        if args[0] == "docker":
            return subprocess.CompletedProcess(args, 0 if container else 1, stdout="running healthy\n" if container else "", stderr="")
        return subprocess.CompletedProcess(args, 0, stdout="LoadState=loaded\nActiveState=inactive\n", stderr="")

    monkeypatch.setattr(engine.subprocess, "run", fake_run)
    assert engine.systemd_state() == expected
    assert asked == (["docker"] if container else ["docker", "systemctl"])

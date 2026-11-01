"""The legal engine sleeps behind systemd socket activation (#161): any connection to it wakes it. Status reads
must ask systemd instead of the engine, a page visit warms it at most once per 5 minutes, and an answer taken
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

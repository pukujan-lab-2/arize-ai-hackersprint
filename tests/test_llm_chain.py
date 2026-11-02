"""The model fallback chain: providers tried in order through an OpenAI-compatible streaming call, optionally via the
Octo vault relay. Every test runs against a fake host that speaks the real wire format."""

import json
import os
import pathlib
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("LLM_MODE", "fake")
from app import llm, llmchain  # noqa: E402


class Fake:
    """Providers live under /<name>/chat/completions. `plan[name]` is a list of behaviours consumed one per request;
    the last one repeats. A behaviour is a dict: status, text, delay (seconds before the first token), stream_error."""

    def __init__(self):
        self.plan, self.calls, self.lease_calls, self.vault_headers = {}, [], 0, []
        self.lease_expires = "2099-01-01T00:00:00Z"
        host = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, status, body, ctype="application/json"):
                data = body if isinstance(body, bytes) else json.dumps(body).encode()
                self.send_response(status)
                self.send_header("content-type", ctype)
                self.send_header("content-length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                host.vault_headers.append(dict(self.headers))
                if self.path == "/api/vault/open":
                    return self._send(200, {"items": [{"id": "item-1", "label": "inferhub"}, {"id": "item-2", "label": "qwen"}]})
                self._send(404, {})

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("content-length") or 0)) or b"{}")
                host.vault_headers.append(dict(self.headers))
                if self.path == "/api/vault/open/lease":
                    host.lease_calls += 1
                    return self._send(
                        201,
                        {
                            "lease": {"itemId": body.get("itemId"), "expiresAt": host.lease_expires},
                            "rawSecret": "octo_tmp_FAKE%d" % host.lease_calls,
                            "proxy": {"url": host.url + "/api/vault/proxy", "targetHeader": "x-octo-target"},
                        },
                    )
                path = self.path
                if self.path == "/api/vault/proxy":
                    path = urlparse(self.headers["x-octo-target"]).path
                name = path.strip("/").split("/")[0]
                host.calls.append({"provider": name, "auth": self.headers.get("authorization"), "via_proxy": self.path == "/api/vault/proxy", "body": body})
                steps = host.plan.get(name) or [{"text": "ok from " + name}]
                n = len([c for c in host.calls if c["provider"] == name])
                step = steps[min(n, len(steps)) - 1]
                if step.get("status", 200) != 200:
                    return self._send(step["status"], {"error": {"message": "nope"}})
                self.send_response(200)
                self.send_header("content-type", "text/event-stream")
                self.send_header("transfer-encoding", "chunked")
                self.end_headers()

                def chunk(data):
                    self.wfile.write(f"{len(data):x}\r\n".encode() + data + b"\r\n")
                    self.wfile.flush()

                time.sleep(step.get("delay", 0))
                if step.get("stream_error"):
                    chunk(b'data: {"error": {"message": "overloaded"}}\n\n')
                else:
                    for word in step.get("text", "").split(" "):
                        if word:
                            chunk(("data: " + json.dumps({"choices": [{"delta": {"content": word + " "}}]}) + "\n\n").encode())
                    if step.get("reasoning"):
                        chunk(("data: " + json.dumps({"choices": [{"delta": {"reasoning_content": "hmm"}}]}) + "\n\n").encode())
                chunk(b"data: [DONE]\n\n")
                self.wfile.write(b"0\r\n\r\n")

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def names(self):
        return [c["provider"] for c in self.calls]

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def fake(monkeypatch, tmp_path):
    f = Fake()
    monkeypatch.setattr(llm, "CACHE", tmp_path)
    monkeypatch.setattr(llm, "COUNT", tmp_path / "_real_calls.json")
    monkeypatch.delenv("LLM_MODE", raising=False)
    for k in ("OCTO_VAULT_GRANT", "OCTO_VAULT_URL", "ANTHROPIC_API_KEY", "INFERHUB_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("K1", "key-one")
    monkeypatch.setenv("K2", "key-two")
    monkeypatch.setenv("K3", "key-three")
    monkeypatch.setattr(llmchain, "BUSY_DELAYS", (0.0, 0.0))
    monkeypatch.setattr(llmchain, "SLOW_START_S", 0.4)
    llmchain._reset()
    llm.LAST_ERR.clear()
    yield f
    f.close()
    llmchain._reset()


def chain(monkeypatch, fake, names=("a", "b", "c"), **extra):
    spec = [{"name": n, "base_url": f"{fake.url}/{n}", "model": f"m-{n}", "key_env": f"K{i + 1}", **extra.get(n, {})} for i, n in enumerate(names)]
    monkeypatch.setenv("LLM_CHAIN", json.dumps(spec))
    llmchain._reset()


def run(prompt="q", **kw):
    return llm.complete("sys", prompt, 300, fallback=lambda: "TEMPLATE", **kw)


def test_off_without_a_chain(monkeypatch):
    monkeypatch.delenv("LLM_CHAIN", raising=False)
    llmchain._reset()
    assert llmchain.configured() is False


def test_first_provider_answers_and_streams(fake, monkeypatch):
    chain(monkeypatch, fake)
    seen = []
    text, provider = llm.complete_stream("sys", "stream q", 300, fallback=lambda: "TEMPLATE", on_delta=seen.append)
    assert text.strip() == "ok from a" and provider == "chain/a/m-a (streamed)"
    assert seen and seen[-1].strip() == "ok from a"
    assert fake.names() == ["a"]
    assert fake.calls[0]["auth"] == "Bearer key-one" and fake.calls[0]["body"]["stream"] is True and fake.calls[0]["body"]["model"] == "m-a"


@pytest.mark.parametrize("step", [{"status": 500}, {"status": 401}, {"status": 404}, {"stream_error": True}, {"text": ""}, {"text": "", "reasoning": True}])
def test_any_failure_moves_to_the_next_provider(fake, monkeypatch, step):
    chain(monkeypatch, fake)
    fake.plan["a"] = [step]
    text, provider = run("fail q")
    assert provider == "chain/b/m-b" and text.strip() == "ok from b"
    assert "a" in llm.LAST_ERR


def test_busy_is_retried_twice_with_backoff_then_succeeds(fake, monkeypatch):
    chain(monkeypatch, fake)
    delays = []
    monkeypatch.setattr(llmchain, "_sleep", lambda s: delays.append(s))
    monkeypatch.setattr(llmchain, "BUSY_DELAYS", (0.6, 1.2))
    fake.plan["a"] = [{"status": 429}, {"status": 503}, {"text": "finally"}]
    text, provider = run("busy q")
    assert provider == "chain/a/m-a" and fake.names() == ["a", "a", "a"]
    assert delays == [0.6, 1.2]


def test_persistent_busy_gives_up_after_the_retries(fake, monkeypatch):
    chain(monkeypatch, fake)
    fake.plan["a"] = [{"status": 429}]
    _, provider = run("busy forever q")
    assert provider == "chain/b/m-b" and fake.names().count("a") == 3


def test_a_provider_slow_to_start_is_dropped_but_the_last_is_waited_for(fake, monkeypatch):
    chain(monkeypatch, fake)
    fake.plan["a"] = [{"delay": 1.5, "text": "late a"}]
    fake.plan["b"] = [{"delay": 1.5, "text": "late b"}]
    fake.plan["c"] = [{"delay": 0.8, "text": "slow but last"}]  # slower than the slow-start limit, still waited for
    started = time.time()
    text, provider = run("slow q")
    assert provider == "chain/c/m-c" and text.strip() == "slow but last"
    assert time.time() - started < 3.5  # a and b were abandoned at the limit, not waited out


def test_all_providers_failing_falls_back_to_the_template(fake, monkeypatch):
    chain(monkeypatch, fake)
    for n in "abc":
        fake.plan[n] = [{"status": 500}]
    text, provider = run("all fail q")
    assert text == "TEMPLATE" and provider.startswith("template")


def test_unhealthy_providers_go_last_but_are_kept(fake, monkeypatch):
    chain(monkeypatch, fake)
    llmchain.set_health({"a": False})
    assert [p.name for p in llmchain.ordered()] == ["b", "c", "a"]
    fake.plan["b"] = [{"status": 500}]
    fake.plan["c"] = [{"status": 500}]
    _, provider = run("last resort q")
    assert provider == "chain/a/m-a"  # the unhealthy one still answers when the others cannot
    llmchain.set_health({"a": True})
    assert [p.name for p in llmchain.ordered()] == ["a", "b", "c"]


def test_the_probe_marks_health_from_a_real_streamed_reply(fake, monkeypatch):
    chain(monkeypatch, fake)
    fake.plan["a"] = [{"status": 500}]
    llmchain.probe_once()
    assert llmchain.health() == {"a": False, "b": True, "c": True}
    assert [p.name for p in llmchain.ordered()][-1] == "a"


def test_answers_are_cached_and_a_cache_hit_calls_no_provider(fake, monkeypatch):
    chain(monkeypatch, fake)
    run("cache q")
    n = len(fake.calls)
    text, provider = run("cache q")
    assert provider.endswith("(cached)") and len(fake.calls) == n


def _vault(monkeypatch, fake):
    monkeypatch.setenv("OCTO_VAULT_URL", fake.url + "/api")
    monkeypatch.setenv("OCTO_VAULT_GRANT", "octo_vault_GRANT")


def test_a_vault_provider_leases_a_key_and_calls_through_the_relay(fake, monkeypatch):
    _vault(monkeypatch, fake)
    chain(monkeypatch, fake, names=("a",), a={"vault": "inferhub", "key_env": None})
    text, provider = run("vault q")
    assert provider == "chain/a/m-a"
    call = fake.calls[0]
    assert call["via_proxy"] is True and call["auth"] == "Bearer octo_tmp_FAKE1"  # the leased working key, never the grant
    assert fake.lease_calls == 1
    run("vault q 2")
    assert fake.lease_calls == 1  # the lease is reused


def test_an_expiring_lease_is_renewed_and_a_refused_key_is_leased_again(fake, monkeypatch):
    _vault(monkeypatch, fake)
    chain(monkeypatch, fake, names=("a", "b"), a={"vault": "inferhub", "key_env": None})
    fake.lease_expires = "2000-01-01T00:00:00Z"  # already within the renewal window
    run("renew q")
    run("renew q 2")
    assert fake.lease_calls == 2  # every use sees an expiring lease and takes a fresh one
    fake.lease_expires = "2099-01-01T00:00:00Z"
    llmchain.renew_leases(force=True)
    assert fake.lease_calls == 3


def test_a_missing_grant_makes_a_vault_provider_fail_cleanly(fake, monkeypatch):
    chain(monkeypatch, fake, names=("a", "b"), a={"vault": "inferhub", "key_env": None})
    text, provider = run("no grant q")
    assert provider == "chain/b/m-b" and "a" in llm.LAST_ERR
    assert fake.lease_calls == 0


def test_errors_never_leak_keys_or_urls(fake, monkeypatch):
    chain(monkeypatch, fake)
    fake.plan["a"] = [{"status": 401}]
    run("leak q")
    assert "key-one" not in json.dumps(llm.LAST_ERR) and "127.0.0.1" not in json.dumps(llm.LAST_ERR)

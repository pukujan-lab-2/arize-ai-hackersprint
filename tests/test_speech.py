"""The shared speech host (speech-to-text and text-to-speech on open models), used by dictation, hands-free mode and
spoken answers. Off unless SPEECH_URL is set; every test runs against a fake host that speaks the real host's API."""

import io
import json
import os
import pathlib
import struct
import sys
import threading
import time
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("LLM_MODE", "fake")
os.environ["ACS_HOTLOAD"] = "0"
from fastapi.testclient import TestClient  # noqa: E402

from app import limits, server, speech, ttschain  # noqa: E402

c = TestClient(server.app)


def make_wav(seconds=1.0, rate=16000):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack("<h", 800) * int(rate * seconds))
    return buf.getvalue()


class FakeHost:
    """The real host's contract: GET /health; POST /stt?lang=&stack= (WAV in, JSON out); POST /tts (JSON in, chunked
    16-bit PCM out with x-sample-rate); POST /load?stack=."""

    def __init__(self):
        self.calls = []
        self.transcript = "can police search my car without a warrant"
        self.stt_status = 200
        self.stt_delay = 0.0
        self.tts_status = 200
        self.tts_samples = 24000  # one second at 24 kHz
        self.active = "multilingual"
        host = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _json(self, status, body):
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                host.calls.append(("GET", self.path, b"", dict(self.headers)))
                if urlparse(self.path).path == "/health":
                    return self._json(
                        200, {"ok": True, "stt": "fake-stt", "tts": "fake-tts", "rate": 24000, "active": host.active, "loaded": ["fake-stt", "fake-tts"]}
                    )
                self._json(404, {})

            def do_POST(self):
                n = int(self.headers.get("content-length") or 0)
                body = self.rfile.read(n)
                host.calls.append(("POST", self.path, body, dict(self.headers)))
                path = urlparse(self.path).path
                if path == "/stt":
                    time.sleep(host.stt_delay)
                    if host.stt_status != 200:
                        return self._json(host.stt_status, {"error": "boom"})
                    return self._json(200, {"text": host.transcript, "language": "en", "ms": 12, "seconds": 1.0, "confidence": 0.9})
                if path == "/tts":
                    if host.tts_status != 200:
                        return self._json(host.tts_status, {"error": "boom"})
                    pcm = struct.pack("<h", 1000) * host.tts_samples
                    self.send_response(200)
                    self.send_header("content-type", "audio/L16")
                    self.send_header("x-sample-rate", "24000")
                    self.send_header("transfer-encoding", "chunked")
                    self.end_headers()
                    for i in range(0, len(pcm), 4096):
                        chunk = pcm[i : i + 4096]
                        self.wfile.write(f"{len(chunk):x}\r\n".encode() + chunk + b"\r\n")
                    self.wfile.write(b"0\r\n\r\n")
                    return
                if path == "/load":
                    host.active = parse_qs(urlparse(self.path).query).get("stack", [host.active])[0]
                    return self._json(200, {"ok": True, "stack": host.active})
                self._json(404, {})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def posts(self, path):
        return [call for call in self.calls if call[0] == "POST" and urlparse(call[1]).path == path]

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def host(monkeypatch, tmp_path):
    for name in ("SPEECH_STACK", "SPEECH_DISABLE", "FISH_API_KEY", "ELEVENLABS_API_KEY", "SPEECH_VOICE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("TTS_CACHE_DIR", str(tmp_path / "tts"))
    monkeypatch.setenv("TTS_DISABLE_KOKORO", "1")
    h = FakeHost()
    monkeypatch.setenv("SPEECH_URL", h.url)
    speech._reset()
    limits._hour["speech_stt"].clear()
    limits._hour["speech_tts"].clear()
    yield h
    h.close()
    speech._reset()


# ---------------- the client ----------------
def test_off_until_a_url_is_set(monkeypatch):
    monkeypatch.delenv("SPEECH_URL", raising=False)
    assert speech.enabled() is False
    assert speech.status()["ok"] is False and speech.status()["reason"] == "not configured"
    monkeypatch.setenv("SPEECH_URL", "http://127.0.0.1:9")
    assert speech.enabled() is True
    monkeypatch.setenv("SPEECH_DISABLE", "1")
    assert speech.enabled() is False


def test_stt_sends_the_wav_and_no_stack_unless_one_is_chosen(host, monkeypatch):
    wav = make_wav()
    out = speech.stt(wav)
    assert out["text"] == host.transcript and out["ms"] == 12
    ((_, path, body, headers),) = host.posts("/stt")
    assert body == wav and headers["Content-Type"] == "audio/wav"
    assert parse_qs(urlparse(path).query) == {"lang": ["en"]}  # no stack: the host's active stack is used
    monkeypatch.setenv("SPEECH_STACK", "parakeet-kokoro")
    speech.stt(wav)
    assert parse_qs(urlparse(host.posts("/stt")[-1][1]).query)["stack"] == ["parakeet-kokoro"]


@pytest.mark.parametrize("status,reason", [(500, "http:500"), (503, "http:503"), (400, "http:400")])
def test_stt_reports_why_it_failed(host, status, reason):
    host.stt_status = status
    with pytest.raises(speech.SpeechError) as e:
        speech.stt(make_wav())
    assert e.value.reason == reason


def test_stt_times_out_and_reports_a_dead_host(host, monkeypatch):
    host.stt_delay = 1.5
    monkeypatch.setenv("SPEECH_STT_TIMEOUT_S", "0.3")
    with pytest.raises(speech.SpeechError) as e:
        speech.stt(make_wav())
    assert e.value.reason == "timeout"
    monkeypatch.setenv("SPEECH_URL", "http://127.0.0.1:9")
    with pytest.raises(speech.SpeechError) as e:
        speech.stt(make_wav())
    assert e.value.reason.startswith("error:")


def test_tts_returns_a_playable_wav_with_its_duration(host):
    out = speech.tts("Colorado requires probable cause.")
    with wave.open(io.BytesIO(out["audio"])) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, 24000)
        assert w.getnframes() == host.tts_samples
    assert out["duration_s"] == pytest.approx(1.0, abs=0.01)
    assert json.loads(host.posts("/tts")[0][2]) == {"text": "Colorado requires probable cause.", "lang": "en"}


def test_status_is_honest_and_follows_the_host(host):
    s = speech.status()
    assert s["ok"] is True and s["active"] == "multilingual" and s["stt"] == "fake-stt"
    host.close()
    speech._reset()
    s = speech.status()
    assert s["ok"] is False and s["reason"].startswith("error:")


def test_warm_loads_the_chosen_stack_only_when_it_is_not_already_active(host, monkeypatch):
    assert speech.warm()["started"] is True
    assert host.posts("/load") == []  # no stack chosen: never swap models
    monkeypatch.setenv("SPEECH_STACK", "multilingual")
    speech._reset()
    speech.warm()
    assert host.posts("/load") == []  # already active: no swap
    monkeypatch.setenv("SPEECH_STACK", "parakeet-kokoro")
    speech._reset()
    speech.warm()
    assert len(host.posts("/load")) == 1


# ---------------- /api/stt ----------------
def upload(data, name="q.wav", ctype="audio/wav"):
    return c.post("/api/stt", files={"file": (name, data, ctype)})


def test_api_stt_uses_the_speech_host(host):
    r = upload(make_wav())
    assert r.status_code == 200
    assert r.json() == {"text": host.transcript, "engine": "speech", "ms": 12}


def test_api_stt_without_any_engine_says_so(monkeypatch):
    monkeypatch.delenv("SPEECH_URL", raising=False)
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    speech._reset()
    r = upload(make_wav())
    assert r.status_code == 503 and "error" in r.json()


def test_api_stt_rejects_what_the_host_cannot_read(host):
    assert upload(b"not audio at all", "q.webm", "audio/webm").status_code == 415
    assert upload(make_wav(seconds=70)).status_code == 413  # more than 2 MB
    assert host.posts("/stt") == []


def test_api_stt_failure_is_a_clear_503_with_the_reason(host):
    host.stt_status = 500
    r = upload(make_wav())
    assert r.status_code == 503
    assert r.json()["reason"] == "http:500" and "error" in r.json()


def test_api_stt_falls_back_to_elevenlabs_only_when_keyed(host, monkeypatch):
    host.stt_status = 500
    seen = {}

    class Resp:
        status_code = 200

        def json(self):
            return {"text": "from the cloud"}

    real_post = server.httpx.post

    def fake_post(url, **kw):
        if "elevenlabs" not in url:
            return real_post(url, **kw)  # the speech host call still goes to the fake host, and fails
        seen["url"] = url
        return Resp()

    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    monkeypatch.setattr(server.httpx, "post", fake_post)
    r = upload(make_wav())
    assert r.status_code == 200 and r.json()["text"] == "from the cloud" and r.json()["engine"] == "elevenlabs"
    assert "elevenlabs" in seen["url"]


def test_api_stt_is_capped_per_hour(host, monkeypatch):
    monkeypatch.setitem(limits.CAPS, "speech_stt", 2)
    assert upload(make_wav()).status_code == 200
    assert upload(make_wav()).status_code == 200
    r = upload(make_wav())
    assert r.status_code == 429
    assert len(host.posts("/stt")) == 2


def test_api_stt_never_writes_the_audio_anywhere(host, monkeypatch, tmp_path):
    writes = []
    real_open = open

    def watching_open(file, mode="r", *a, **kw):
        if any(m in mode for m in "wax+") and str(file).endswith((".wav", ".webm", ".mp3", ".pcm", ".bin")):
            writes.append(str(file))
        return real_open(file, mode, *a, **kw)

    monkeypatch.setattr("builtins.open", watching_open)
    monkeypatch.setattr(pathlib.Path, "write_bytes", lambda self, data: writes.append(str(self)))
    assert upload(make_wav()).status_code == 200
    assert writes == []


# ---------------- speech output through the TTS chain ----------------
def test_the_chain_puts_the_speech_host_first_and_caches_its_clips(host):
    assert ttschain.chain() == ["speech", "browser"]
    first, tried = ttschain.synth("Colorado requires probable cause for a car search.")
    assert first["provider"] == "speech" and first["audio"][:4] == b"RIFF" and first["cache"] == "miss"
    assert tried[0]["provider"] == "speech" and tried[0]["result"] == "ok"
    again, _ = ttschain.synth("Colorado requires probable cause for a car search.")
    assert again["cache"] == "hit" and again["audio"] == first["audio"]
    assert len(host.posts("/tts")) == 1  # the second line never reached the host


def test_a_failing_host_falls_through_and_is_reported(host):
    host.tts_status = 500
    res, tried = ttschain.synth("A line the host cannot speak.")
    assert res is None and tried[0] == {"provider": "speech", "result": "http:500", "ms": tried[0]["ms"]}


def test_health_lists_speech_only_while_it_is_reachable(host):
    assert "speech" in ttschain.health()["tts"]
    host.close()
    speech._reset()
    assert "speech" not in ttschain.health()["tts"]


def test_the_endpoints_label_wav_clips_correctly(host):
    r = c.post("/api/tts", json={"text": "A clip to label."})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/wav" and r.headers["X-TTS-Provider"] == "speech"
    j = c.post("/api/tts_ts", json={"text": "A clip to label."}).json()
    assert j["provider"] == "speech" and j["format"] == "wav" and j["cache"] == "hit"


def test_api_health_reports_the_speech_host(host):
    h = c.get("/api/health").json()
    assert h["speech"]["ok"] is True and h["speech"]["active"] == "multilingual"


def test_warm_endpoint(host, monkeypatch):
    r = c.post("/api/speech/warm")
    assert r.status_code == 200 and r.json()["started"] is True
    monkeypatch.delenv("SPEECH_URL")
    speech._reset()
    assert c.post("/api/speech/warm").json() == {"started": False, "reason": "off"}

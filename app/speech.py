"""Client for the shared speech host: speech-to-text and text-to-speech on small open models (Parakeet / Whisper,
Kokoro / Pocket), run on the machine named by SPEECH_URL. Off until that is set.

The host is shared with other tools, so this client never swaps its models on its own: a stack is only requested when
SPEECH_STACK is set. Audio is passed through and never written to disk here."""

import io
import os
import threading
import time
import wave

import httpx

_st = {"t": 0.0, "v": None}
_lock = threading.Lock()


class SpeechError(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def _f(name, default):
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return float(default)


def url():
    return (os.environ.get("SPEECH_URL") or "").rstrip("/")


def enabled():
    return bool(url()) and os.environ.get("SPEECH_DISABLE", "") in ("", "0")


def stack():
    return os.environ.get("SPEECH_STACK", "")


def voice():
    return os.environ.get("SPEECH_VOICE") or stack() or "default"


def _reset():
    with _lock:
        _st.update(t=0.0, v=None)


def _why(e):
    if isinstance(e, httpx.TimeoutException):
        return "timeout"
    return "error:" + type(e).__name__


def status():
    """The host's own /health, cached 15s so /api/health stays cheap."""
    if not enabled():
        return {"ok": False, "reason": "not configured"}
    with _lock:
        if _st["v"] is not None and time.time() - _st["t"] < 15:
            return _st["v"]
    try:
        r = httpx.get(url() + "/health", timeout=_f("SPEECH_HEALTH_TIMEOUT_S", 1.0))
        v = {"ok": True, **{k: r.json().get(k) for k in ("active", "stt", "tts", "loaded") if k in r.json()}} if r.status_code == 200 else {"ok": False, "reason": "http:%d" % r.status_code}
    except Exception as e:
        v = {"ok": False, "reason": _why(e)}
    with _lock:
        _st.update(t=time.time(), v=v)
    return v


def stt(wav, lang="en"):
    """Transcribe a WAV. Returns the host's JSON ({text, ms, ...}); raises SpeechError(reason)."""
    params = {"lang": lang}
    if stack():
        params["stack"] = stack()
    try:
        r = httpx.post(url() + "/stt", params=params, content=wav, headers={"Content-Type": "audio/wav"}, timeout=_f("SPEECH_STT_TIMEOUT_S", 30))
    except Exception as e:
        raise SpeechError(_why(e))
    if r.status_code != 200:
        raise SpeechError("http:%d" % r.status_code)
    try:
        return r.json()
    except ValueError:
        raise SpeechError("bad-json")


def tts(text, lang="en"):
    """Speak one line. Returns {audio: WAV bytes, duration_s}; the host streams raw 16-bit PCM, wrapped here."""
    body = {"text": text, "lang": lang}
    if stack():
        body["stack"] = stack()
    try:
        with httpx.stream("POST", url() + "/tts", json=body, timeout=_f("SPEECH_TTS_TIMEOUT_S", 20)) as r:
            if r.status_code != 200:
                raise SpeechError("http:%d" % r.status_code)
            try:
                rate = int(r.headers.get("x-sample-rate") or 24000)
            except ValueError:
                rate = 24000
            pcm = b"".join(r.iter_bytes())
    except SpeechError:
        raise
    except Exception as e:
        raise SpeechError(_why(e))
    if not pcm:
        raise SpeechError("empty")
    pcm = pcm[: len(pcm) - len(pcm) % 2]
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return {"audio": buf.getvalue(), "duration_s": round(len(pcm) / 2 / rate, 3)}


def warm():
    """Wake the host for an expected request. Loads the chosen stack only if it is not already the active one."""
    if not enabled():
        return {"started": False, "reason": "off"}
    s = status()
    if not s.get("ok"):
        return {"started": False, "reason": s.get("reason", "down")}
    want = stack()
    if want and s.get("active") != want:
        try:
            httpx.post(url() + "/load", params={"stack": want}, timeout=_f("SPEECH_LOAD_TIMEOUT_S", 60))
        except Exception as e:
            return {"started": False, "reason": _why(e)}
        _reset()
    return {"started": True}

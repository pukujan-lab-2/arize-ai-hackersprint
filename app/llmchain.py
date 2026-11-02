"""The model fallback chain. Providers are tried in order through an OpenAI-compatible streaming call, each either
direct (a key in the environment) or through the Octo vault relay (a leased working key; the real key never leaves
the vault). Off until LLM_CHAIN is set, so nothing changes without it.

LLM_CHAIN is a JSON list, in order, of {"name", "base_url", "model", and "key_env" or "vault" (an item label), optional
"extra" (fields added to the request body), optional "max_tokens_floor"}. The vault relay needs OCTO_VAULT_GRANT.

Within one question: any failure moves to the next provider; a busy answer is retried twice first (0.6 s, then 1.2 s);
a provider that has not started answering after 6 s is dropped for the next; the last provider is waited for.
A watcher probes each provider every five minutes and moves ones that failed to the back of the line (kept as a last
resort); it also renews the vault leases once a day. State is in memory, one set per server process."""

import datetime
import json
import os
import threading
import time
from dataclasses import dataclass, field

import httpx

_sleep = time.sleep  # a name of our own, so a test can watch the back-off without slowing everything else
BUSY_STATUS = (429, 503, 529)
BUSY_DELAYS = (0.6, 1.2)
SLOW_START_S = 6.0
LAST_WAIT_S = 30.0
PROBE_EVERY_S = 300.0
PROBE_TIMEOUT_S = 20.0
RENEW_EVERY_S = 86400.0
RENEW_WINDOW_S = 86400.0

_lock = threading.RLock()
_state: dict = {"cfg": None, "health": {}, "probed": {}, "leases": {}, "items": None, "watcher": None}


class ChainFailed(Exception):
    pass


class ProviderError(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


class Busy(Exception):
    pass


@dataclass
class Provider:
    name: str
    base_url: str
    model: str
    key_env: str = ""
    vault: str = ""
    extra: dict = field(default_factory=dict)
    max_tokens_floor: int = 0


def _reset():
    with _lock:
        _state.update(cfg=None, health={}, probed={}, leases={}, items=None)


def providers():
    with _lock:
        if _state["cfg"] is not None:
            return _state["cfg"]
    out = []
    raw = os.environ.get("LLM_CHAIN", "").strip()
    if raw:
        try:
            for spec in json.loads(raw):
                out.append(
                    Provider(
                        name=str(spec["name"]),
                        base_url=str(spec["base_url"]).rstrip("/"),
                        model=str(spec["model"]),
                        key_env=str(spec.get("key_env") or ""),
                        vault=str(spec.get("vault") or ""),
                        extra=dict(spec.get("extra") or {}),
                        max_tokens_floor=int(spec.get("max_tokens_floor") or 0),
                    )
                )
        except (ValueError, KeyError, TypeError):
            out = []  # a malformed chain is no chain: the app falls back to its built-in path, never to a half list
    with _lock:
        _state["cfg"] = out
    return out


def configured():
    return bool(providers())


# ---------------- health
def set_health(values):
    with _lock:
        _state["health"].update(values)


def health():
    with _lock:
        return {p.name: _state["health"].get(p.name, True) for p in providers()}  # not yet probed counts as healthy


def ordered():
    h = health()
    return sorted(providers(), key=lambda p: not h[p.name])  # stable: healthy first, order kept within each group


def status():
    h, probed = health(), dict(_state["probed"])
    return {"chain": [{"name": p.name, "model": p.model, "healthy": h[p.name], "probed_at": probed.get(p.name)} for p in providers()]}


# ---------------- vault relay
def _vault_url():
    return (os.environ.get("OCTO_VAULT_URL") or "https://octodb.design-bakery.com/api").rstrip("/")


def _vault_headers():
    grant = os.environ.get("OCTO_VAULT_GRANT", "")
    if not grant:
        raise ProviderError("no vault grant")
    return {"Authorization": "Bearer " + grant, "User-Agent": "precedent-app/1.0"}


def _item_id(label):
    with _lock:
        items = _state["items"]
    if items is None:
        r = httpx.get(_vault_url() + "/vault/open", headers=_vault_headers(), timeout=15)
        r.raise_for_status()
        items = {i["label"]: i["id"] for i in r.json().get("items", [])}
        with _lock:
            _state["items"] = items
    if label not in items:
        raise ProviderError("vault item missing")
    return items[label]


def _expires(value):
    try:
        return datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _lease(label, force=False):
    """The working key for a vault item: reused until it is within a day of expiring."""
    with _lock:
        held = _state["leases"].get(label)
    if held and not force and held["expires"] - time.time() > RENEW_WINDOW_S:
        return held
    try:
        r = httpx.post(_vault_url() + "/vault/open/lease", headers=_vault_headers(), json={"itemId": _item_id(label)}, timeout=15)
        r.raise_for_status()
        j = r.json()
        held = {
            "secret": j["rawSecret"],
            "proxy": j["proxy"]["url"],
            "target_header": j["proxy"].get("targetHeader") or "x-octo-target",
            "expires": _expires((j.get("lease") or {}).get("expiresAt")),
        }
    except ProviderError:
        raise
    except Exception as e:
        raise ProviderError("lease:" + type(e).__name__)
    with _lock:
        _state["leases"][label] = held
    return held


def renew_leases(force=False):
    for p in providers():
        if p.vault:
            try:
                _lease(p.vault, force=force)
            except ProviderError:
                pass


# ---------------- one provider
def _request(p):
    """(url, headers) for one call: direct with its key, or through the relay with a leased working key."""
    target = p.base_url + "/chat/completions"
    if p.vault:
        lease = _lease(p.vault)
        return lease["proxy"], {"Authorization": "Bearer " + lease["secret"], lease["target_header"]: target, "User-Agent": "precedent-app/1.0"}
    key = os.environ.get(p.key_env, "") if p.key_env else ""
    if not key:
        raise ProviderError("no key")
    return target, {"Authorization": "Bearer " + key}


def _stream_once(p, system, prompt, mt, on_delta, read_s):
    url, headers = _request(p)
    body = {
        "model": p.model,
        "max_tokens": max(mt, p.max_tokens_floor),
        "stream": True,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        **p.extra,
    }
    out = []
    try:
        with httpx.stream("POST", url, headers=headers, json=body, timeout=httpx.Timeout(connect=6.0, read=read_s, write=10.0, pool=6.0)) as r:
            if r.status_code in BUSY_STATUS:
                raise Busy()
            if r.status_code != 200:
                if r.status_code in (401, 403) and p.vault:
                    with _lock:
                        _state["leases"].pop(p.vault, None)  # refused: take a fresh key next time
                raise ProviderError("http:%d" % r.status_code)
            for line in r.iter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    event = json.loads(data)
                except ValueError:
                    continue
                if event.get("error"):
                    raise ProviderError("stream-error")
                delta = ((event.get("choices") or [{}])[0].get("delta") or {}).get("content")
                if delta:
                    out.append(delta)
                    if on_delta:
                        on_delta("".join(out))
    except (Busy, ProviderError):
        raise
    except httpx.TimeoutException:
        raise ProviderError("slow" if not out else "timeout")
    except Exception as e:
        raise ProviderError("error:" + type(e).__name__)
    text = "".join(out).strip()
    if not text:
        raise ProviderError("empty")
    return text


def _call(p, system, prompt, mt, on_delta, last):
    for attempt in range(len(BUSY_DELAYS) + 1):
        try:
            return _stream_once(p, system, prompt, mt, on_delta, LAST_WAIT_S if last else SLOW_START_S)
        except Busy:
            if attempt < len(BUSY_DELAYS):
                _sleep(BUSY_DELAYS[attempt])
                continue
            raise ProviderError("busy")


def run(system, prompt, max_tokens, on_delta=None):
    """(text, label) from the first provider that answers; raises ChainFailed when none does."""
    from app import llm  # imported here: llm imports this module

    order = ordered()
    for i, p in enumerate(order):
        try:
            text = _call(p, system, prompt, max_tokens, on_delta, last=i == len(order) - 1)
        except ProviderError as e:
            llm.LAST_ERR[p.name] = e.reason  # a reason, never a message: nothing here can carry a key or an address
            continue
        return text, f"chain/{p.name}/{p.model}"
    raise ChainFailed()


# ---------------- watcher
def probe_once():
    """Ask every provider for a one-word reply and record who answered."""
    for p in providers():
        ok = True
        try:
            _stream_once(p, "Reply with the single word OK.", "Say OK.", 16, None, PROBE_TIMEOUT_S)
        except (Busy, ProviderError):
            ok = False
        with _lock:
            _state["health"][p.name] = ok
            _state["probed"][p.name] = datetime.datetime.now(datetime.timezone.utc).isoformat()


def _watch():
    renewed = 0.0
    while True:
        try:
            probe_once()
            if time.time() - renewed >= RENEW_EVERY_S:
                renew_leases(force=True)
                renewed = time.time()
        except Exception:
            pass
        time.sleep(PROBE_EVERY_S)


def start_watcher():
    """Start the probe and renewal loop once per process, if a chain is configured."""
    with _lock:
        if _state["watcher"] is not None or os.environ.get("LLM_WATCHER", "1") == "0" or not providers():
            return False
        _state["watcher"] = threading.Thread(target=_watch, daemon=True, name="llm-watcher")
        _state["watcher"].start()
    return True

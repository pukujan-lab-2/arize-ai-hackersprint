"""Eval scores become Phoenix span annotations, and the LLM span names its model."""

import threading

from app import agents, tracing


class _Ctx:
    span_id = 0xABCDEF


class _Span:
    def get_span_context(self):
        return _Ctx()


def test_the_model_name_comes_out_of_the_provider_label():
    assert agents._model_name("inferhub/cb/deepseek-v4.1-flash (cached)") == "cb/deepseek-v4.1-flash"
    assert agents._model_name("anthropic/claude-haiku-4-5") == "claude-haiku-4-5"
    assert agents._model_name("template (offline)") == "template"
    assert agents._model_name("") == "unknown"


def test_annotations_post_each_score_for_the_span(monkeypatch):
    sent = {}

    class Reply:
        status_code = 200

    def fake_post(url, json, headers, timeout):
        sent.update(url=url, json=json, headers=headers)
        return Reply()

    import httpx

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(tracing, "ANNOTATE_DELAYS", (0,))
    assert tracing._post_annotations("00000000000abcdef", {"support": {"label": "fail", "score": 0.1}}, "k")
    row = sent["json"]["data"][0]
    assert row["name"] == "support" and row["result"] == {"label": "fail", "score": 0.1}
    assert sent["url"].endswith("/otel/v1/span_annotations") and sent["headers"]["Authorization"] == "Bearer k"


def test_a_span_not_yet_in_phoenix_is_retried(monkeypatch):
    import httpx

    codes = iter([404, 200])

    class Reply:
        def __init__(self):
            self.status_code = next(codes)

    monkeypatch.setattr(httpx, "post", lambda *a, **k: Reply())
    monkeypatch.setattr(tracing, "ANNOTATE_DELAYS", (0, 0))
    assert tracing._post_annotations("s", {"a": {"label": "x"}}, "k")


def test_annotate_is_a_no_op_without_a_span_or_key(monkeypatch):
    before = threading.active_count()
    monkeypatch.delenv("OCTO_API_KEY", raising=False)
    monkeypatch.delenv("octo_db_legal", raising=False)
    tracing.annotate(_Span(), {"a": {"label": "x"}})
    tracing.annotate(None, {"a": {"label": "x"}})
    assert threading.active_count() == before

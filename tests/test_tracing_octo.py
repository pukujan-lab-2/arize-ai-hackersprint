"""Tracing goes to Octo's Phoenix, with the Octo key; it is off, and says why, when that is not configured."""

import importlib

import pytest

from app import tracing

WS = "76d7577b-2274-42b4-a8dc-1ff1c0efa741"


@pytest.fixture
def fresh(monkeypatch):
    """A tracing module with no tracer yet, and none of the Octo or Arize settings in the environment."""
    for name in ("OCTO_API_KEY", "octo_db_legal", "OCTO_TRACES", "OCTO_WORKSPACE_ID", "OCTO_BASE_URL", "ARIZE_API_KEY", "ARIZE_SPACE_ID"):
        monkeypatch.delenv(name, raising=False)
    module = importlib.reload(tracing)
    yield module
    importlib.reload(tracing)


def test_not_configured_without_an_octo_key(fresh):
    status = fresh.status()
    assert status["ok"] is False
    assert status["reason"] == "not configured"
    assert fresh.enabled() is False


def test_arize_keys_alone_no_longer_turn_tracing_on(fresh, monkeypatch):
    monkeypatch.setenv("ARIZE_API_KEY", "k")
    monkeypatch.setenv("ARIZE_SPACE_ID", "s")
    assert fresh.enabled() is False
    assert fresh.status()["reason"] == "not configured"


def test_octo_traces_off_switches_it_off(fresh, monkeypatch):
    monkeypatch.setenv("OCTO_API_KEY", "key")
    monkeypatch.setenv("OCTO_TRACES", "off")
    assert fresh.enabled() is False
    assert fresh.status()["reason"] == "not configured"


def test_sends_otlp_to_the_workspace_traces_route_with_the_octo_key(fresh, monkeypatch):
    monkeypatch.setenv("OCTO_API_KEY", "secret-key")
    monkeypatch.setenv("OCTO_WORKSPACE_ID", WS)
    monkeypatch.setenv("OCTO_BASE_URL", "https://octo.example/api")
    seen = {}

    class Exporter:
        def __init__(self, endpoint=None, headers=None, **_):
            seen["endpoint"], seen["headers"] = endpoint, headers

        def export(self, spans):
            return None

        def shutdown(self):
            pass

        def force_flush(self, *_args, **_kwargs):
            return True

    monkeypatch.setattr("opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter", Exporter)
    assert fresh.enabled() is True
    assert seen["endpoint"] == f"https://octo.example/api/workspaces/{WS}/otel/v1/traces"
    assert seen["headers"]["Authorization"] == "Bearer secret-key"
    status = fresh.status()
    assert status["ok"] is False  # nothing has been exported yet, and the app does not claim otherwise
    assert status["reason"] == "no span has been exported yet"
    assert status["project"] == "octo-phoenix"


def test_the_legacy_octo_key_name_is_accepted(fresh, monkeypatch):
    monkeypatch.setenv("octo_db_legal", "legacy-key")
    assert fresh.enabled() is True


def test_a_delivered_span_flips_the_status_to_ok(fresh, monkeypatch):
    """The status must follow the exporter whatever shape the installed SDK has; spans that arrive count."""
    from opentelemetry.sdk.trace.export import SpanExportResult

    monkeypatch.setenv("OCTO_API_KEY", "key")

    class Exporter:
        def __init__(self, **_):
            self.batches = 0

        def export(self, spans):
            self.batches += 1
            return SpanExportResult.SUCCESS

        def shutdown(self):
            pass

        def force_flush(self, *_args, **_kwargs):
            return True

    monkeypatch.setattr("opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter", Exporter)
    with fresh.span("pipeline"):
        pass
    fresh._provider.force_flush()
    status = fresh.status()
    assert status["ok"] is True
    assert status["sent"] >= 1
    assert "reason" not in status


def test_a_rejected_batch_is_reported_as_the_reason(fresh, monkeypatch):
    from opentelemetry.sdk.trace.export import SpanExportResult

    monkeypatch.setenv("OCTO_API_KEY", "key")

    class Exporter:
        def __init__(self, **_):
            pass

        def export(self, spans):
            return SpanExportResult.FAILURE

        def shutdown(self):
            pass

        def force_flush(self, *_args, **_kwargs):
            return True

    monkeypatch.setattr("opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter", Exporter)
    with fresh.span("pipeline"):
        pass
    fresh._provider.force_flush()
    status = fresh.status()
    assert status["ok"] is False
    assert status["reason"] == "FAILURE"

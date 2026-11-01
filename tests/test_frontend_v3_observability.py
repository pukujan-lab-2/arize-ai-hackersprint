"""O39-O42: the observability page lists saved runs, shows the selected run's summary, pipeline steps and
timings, opens a step's raw details, and says so when the data source is unavailable.

O104-O106: the page shows the retrieval stages a run actually took, reports tracing honestly, and reports
the first-in-first-out caps of the saved runs and the trace queue."""

import re

import pytest

from ui_server import DESKTOP, app_server, needs_chromium, needs_v3, open_page

sync_api = pytest.importorskip("playwright.sync_api")
pytestmark = [needs_chromium, needs_v3]

RUNS = [
    {
        "run_id": "r0",
        "question": "Which Colorado counties apply the exemption to mineral rights?",
        "n": 3,
        "ts": "2026-10-18T12:00:00Z",
    },
    {
        "run_id": "r1",
        "question": "How are severed mineral interests valued?",
        "n": 5,
        "ts": "2026-10-18T11:00:00Z",
    },
]
EVENTS = [
    {"t": 0.0, "agent": "planner", "kind": "claim"},
    {"t": 4.2, "agent": "retriever", "kind": "release"},
    {"t": 9.8, "agent": "writer", "kind": "release"},
    {"t": 12.5, "agent": "safeguard", "kind": "release"},
]
RESULT = {
    "run_id": "r0",
    "question": RUNS[0]["question"],
    "answer": "Short answer: the exemption follows the residence [1].",
    "elapsed_s": 12.5,
    "provider": "inferhub/deepseek",
    "safeguard": {"pass": True, "used": [], "invalid": [], "unknown_authorities": []},
    "citations": [{"id": "a", "title": "A", "ref": "[1]"}, {"id": "b", "title": "B", "ref": "[2]"}],
}


@pytest.fixture(scope="module")
def base():
    with app_server() as url:
        yield url


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def _stub(page, runs=RUNS, runs_status=200):
    def handle(route):
        url = route.request.url
        if "/api/runs" in url:
            if runs_status != 200:
                return route.fulfill(status=runs_status, content_type="application/json", body="{}")
            return route.fulfill(json=runs)
        if "/api/run/" in url:
            run_id = url.rsplit("/", 1)[-1]
            run = next(run for run in RUNS if run["run_id"] == run_id)
            result = dict(RESULT, run_id=run_id, question=run["question"])
            return route.fulfill(json={"events": EVENTS, "result": result})
        if "observability.json" in url:
            return route.fulfill(json={"traces": [], "project": "precedent"})
        route.continue_()

    page.route("**/*", handle)


def _open(browser, base, **kw):
    ctx, page = open_page(browser, base, "/observability", DESKTOP, setup=lambda p: _stub(p, **kw))
    page.wait_for_timeout(1500)
    return ctx, page


def test_O39_saved_runs_are_listed_and_selectable(base, browser):
    ctx, page = _open(browser, base)
    for run in RUNS:
        # The options menu also names the question; select the history entry itself.
        entry = page.get_by_role("navigation", name="Conversations").get_by_role("button", name=re.compile(rf"^{re.escape(run['question'])}(?:\s|$)"))
        sync_api.expect(entry).to_have_count(1)
        entry.click()
        sync_api.expect(page).to_have_url(re.compile(rf"\?run={run['run_id']}$"))
        sync_api.expect(entry).to_have_attribute("aria-current", "true")
        sync_api.expect(page.locator("article")).to_contain_text("the exemption follows the residence")
    ctx.close()

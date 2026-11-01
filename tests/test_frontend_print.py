"""Printing a memo excludes app controls, including menus still animating closed."""

import pytest

from ui_server import app_server, load_fixture, needs_chromium, needs_v3, serve_run

sync_api = pytest.importorskip("playwright.sync_api")
pytestmark = [needs_chromium, needs_v3]


def test_print_report_excludes_the_export_menu():
    with app_server() as base, sync_api.sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        # Freeze animations when the dialog would open, so an exiting menu stays mounted.
        page.add_init_script("window.print = () => { document.getAnimations().forEach(a => a.pause()); window.__printRequested = true; }")
        run = load_fixture("run-parity.json")
        serve_run(page, run, "print-check")
        page.goto(base + "/?run=print-check")
        page.get_by_role("button", name="Export, print or share").click()
        page.get_by_role("menuitem", name="Save as PDF", exact=True).click()
        page.wait_for_function("window.__printRequested === true")
        menu = page.get_by_role("menu", include_hidden=True)
        assert menu.count() == 1, "The closing export menu must still be mounted for this regression check"
        page.emulate_media(media="print")
        sync_api.expect(page.get_by_role("heading", name=run["question"], exact=True)).to_be_visible()
        sync_api.expect(page.get_by_role("heading", name=f"Authorities ({len(run['citations'])})", exact=True)).to_be_visible()
        sync_api.expect(menu).to_be_hidden()
        page.evaluate("window.dispatchEvent(new Event('afterprint'))")
        page.emulate_media(media="screen")
        sync_api.expect(page.get_by_role("button", name="Export, print or share")).to_be_visible()
        browser.close()

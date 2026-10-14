# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Drive the real dashboard in headless Chromium."""

from collections.abc import Iterator

import pytest
from playwright.sync_api import Page, sync_playwright

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def page() -> Iterator[Page]:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        yield browser.new_page(viewport={"width": 1280, "height": 900})
        browser.close()


def test_navigate_to_blink_test_and_see_plots(page: Page, server_url: str) -> None:
    page.goto(server_url)
    assert page.locator("h1").inner_text() == "What did we record?"
    assert page.locator("table.recordings tbody tr").count() == 6
    page.click("text=blink-test")
    page.wait_for_url("**/recordings/blink-test")
    assert "Detection vs. protocol: 10/10" in page.content()
    images = page.locator("figure.plot img")
    assert images.count() == 3
    for i in range(3):
        img = images.nth(i)
        img.scroll_into_view_if_needed()
        page.wait_for_function(
            "img => img.complete && img.naturalWidth > 0", arg=img.element_handle()
        )


def test_recording_page_back_navigation(page: Page, server_url: str) -> None:
    page.goto(f"{server_url}/recordings/session4")
    assert "Impedance before this session" in page.content()
    page.click(".crumbs a")
    page.wait_for_url(f"{server_url}/")
    assert page.locator(".check.ok").inner_text() == "Manifest check: all files verified"

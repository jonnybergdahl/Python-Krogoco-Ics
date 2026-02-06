"""Tests for scrape_events using the calendar fixture from the screenshot."""

from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from krog_company_ics import KrogocoIcs

FIXTURES = Path(__file__).parent / "fixtures"
CALENDAR_HTML = (FIXTURES / "calendar.html").read_text(encoding="utf-8")
# Use a fixed "today" so the fixture events are always in the future.
FAKE_TODAY = date(2025, 2, 1)


@pytest.fixture()
def events():
    """Scrape the fixture HTML and return the event list."""
    scraper = KrogocoIcs(
        url="https://krogoco.se/jonkoping/kalender/",
        months=2,
    )
    with (
        patch.object(scraper, "_fetch_html", return_value=CALENDAR_HTML),
        patch("krog_company_ics.krogoco_ics.date") as mock_date,
    ):
        mock_date.today.return_value = FAKE_TODAY
        mock_date.side_effect = lambda *args, **kw: date(*args, **kw)
        result = scraper.scrape_events()
    return result


def test_total_event_count(events):
    """All 10 events from the fixture should be scraped."""
    assert len(events) == 10


def test_hv71_skelleftea(events):
    """First event: all-day hockey match on Feb 5."""
    ev = events[0]
    assert ev.title == "HV71 – Skellefteå AIK"
    assert ev.date == date(2025, 2, 5)
    assert ev.all_day is True
    assert ev.url == "https://krogoco.se/jonkoping/event/hv71-skelleftea-aik/"


def test_aw_med_quiz(events):
    """AW Med Quiz with time 'Från Kl.17.00' → start 17:00, no end."""
    ev = events[1]
    assert ev.title == "AW Med Quiz! Från Kl.17.00"
    assert ev.date == date(2025, 2, 6)
    assert ev.all_day is False
    assert ev.start_time == "17:00"
    assert ev.end_time is None


def test_aw_med_mexiko_tema(events):
    """AW Med Mexiko Tema: no time info → all-day."""
    ev = events[2]
    assert ev.title == "AW Med Mexiko Tema"
    assert ev.date == date(2025, 2, 6)
    assert ev.all_day is True


def test_fredagslunch(events):
    """Fredagslunch with 'Kl.12-17' → range 12:00–17:00."""
    ev = events[3]
    assert ev.title == "Fredagslunch Kl.12-17"
    assert ev.date == date(2025, 2, 6)
    assert ev.all_day is False
    assert ev.start_time == "12:00"
    assert ev.end_time == "17:00"


def test_red_velvet_rewind(events):
    """Red Velvet Rewind with 'Från 21:00' → start 21:00, no end."""
    ev = events[4]
    assert ev.title == "Red Velvet Rewind M Dansgolv Från 21:00"
    assert ev.date == date(2025, 2, 6)
    assert ev.all_day is False
    assert ev.start_time == "21:00"
    assert ev.end_time is None


def test_malmo_redhawks(events):
    """Malmö Redhawks – HV71: all-day on Feb 7."""
    ev = events[5]
    assert ev.title == "Malmö Redhawks – HV71"
    assert ev.date == date(2025, 2, 7)
    assert ev.all_day is True


def test_pianobar(events):
    """Pianobar with 'Kl.22.00, 23+' → 22:00–23:00."""
    ev = events[6]
    assert ev.title == "Pianobar Kl.22.00, 23+"
    assert ev.date == date(2025, 2, 7)
    assert ev.all_day is False
    assert ev.start_time == "22:00"
    assert ev.end_time == "23:00"


def test_studentfest(events):
    """Studentfest: no time info → all-day on Feb 11."""
    ev = events[7]
    assert ev.title == "Studentfest"
    assert ev.date == date(2025, 2, 11)
    assert ev.all_day is True
    assert ev.url == "https://krogoco.se/jonkoping/event/studentfest/"


# --- Blacklist tests ---


def _scrape_with_blacklist(blacklist):
    """Helper: scrape fixture HTML with a given blacklist."""
    scraper = KrogocoIcs(
        url="https://krogoco.se/jonkoping/kalender/",
        months=2,
        blacklist=blacklist,
    )
    with (
        patch.object(scraper, "_fetch_html", return_value=CALENDAR_HTML),
        patch("krog_company_ics.krogoco_ics.date") as mock_date,
    ):
        mock_date.today.return_value = FAKE_TODAY
        mock_date.side_effect = lambda *args, **kw: date(*args, **kw)
        return scraper.scrape_events()


def test_blacklist_removes_event():
    """A blacklisted title should be excluded from results."""
    events = _scrape_with_blacklist(["Studentfest"])
    titles = [e.title for e in events]
    assert "Studentfest" not in titles
    assert len(events) == 9


def test_blacklist_case_insensitive():
    """Blacklist matching should be case-insensitive."""
    events = _scrape_with_blacklist(["studentfest"])
    titles = [e.title for e in events]
    assert "Studentfest" not in titles


def test_blacklist_multiple():
    """Multiple blacklisted titles should all be excluded."""
    events = _scrape_with_blacklist(["Studentfest", "AW Med Mexiko Tema"])
    titles = [e.title for e in events]
    assert "Studentfest" not in titles
    assert "AW Med Mexiko Tema" not in titles
    assert len(events) == 8


def test_blacklist_empty():
    """An empty blacklist should not filter anything."""
    events = _scrape_with_blacklist([])
    assert len(events) == 10


def test_blacklist_no_match():
    """A blacklist with no matching titles should not filter anything."""
    events = _scrape_with_blacklist(["Nonexistent Event"])
    assert len(events) == 10


def test_blacklist_sports_keywords():
    """Blacklisting sports keywords should filter matching events by substring."""
    blacklist = ["HV71", "SHL", "hemma", "borta", "match"]
    events = _scrape_with_blacklist(blacklist)
    titles = [e.title for e in events]

    # "HV71" should filter: "HV71 – Skellefteå AIK" and "Malmö Redhawks – HV71"
    assert "HV71 – Skellefteå AIK" not in titles
    assert "Malmö Redhawks – HV71" not in titles

    # "SHL" should filter: "Kval i SHL"
    assert "Kval i SHL" not in titles

    # "match" should filter: "Match J-Södra"
    assert "Match J-Södra" not in titles

    # These should remain (no keyword match)
    assert "AW Med Quiz! Från Kl.17.00" in titles
    assert "AW Med Mexiko Tema" in titles
    assert "Fredagslunch Kl.12-17" in titles
    assert "Red Velvet Rewind M Dansgolv Från 21:00" in titles
    assert "Pianobar Kl.22.00, 23+" in titles
    assert "Studentfest" in titles

    assert len(events) == 6


# --- Duplicate tests ---

DUPLICATE_HTML = (FIXTURES / "calendar_duplicates.html").read_text(encoding="utf-8")


def test_duplicate_events_are_removed():
    """Duplicate events in the source HTML should be deduplicated."""
    scraper = KrogocoIcs(
        url="https://krogoco.se/jonkoping/kalender/",
        months=2,
    )
    with (
        patch.object(scraper, "_fetch_html", return_value=DUPLICATE_HTML),
        patch("krog_company_ics.krogoco_ics.date") as mock_date,
    ):
        mock_date.today.return_value = FAKE_TODAY
        mock_date.side_effect = lambda *args, **kw: date(*args, **kw)
        events = scraper.scrape_events()

    assert len(events) == 2
    assert events[0].title == "Räkfrossa"
    assert events[0].date == date(2025, 2, 28)
    assert events[1].title == "AW Med Quiz! Från Kl.17.00"
    assert events[1].date == date(2025, 3, 6)

"""Tests for year rollover handling in scrape_events."""

from datetime import date
from pathlib import Path
from unittest.mock import patch

from krog_company_ics import KrogocoIcs

FIXTURES = Path(__file__).parent / "fixtures"
ROLLOVER_HTML = (FIXTURES / "calendar_year_rollover.html").read_text(encoding="utf-8")

ROLLOVER_TODAY = date(2025, 11, 1)


def _scrape_rollover(months):
    """Helper: scrape the year rollover fixture."""
    scraper = KrogocoIcs(
        url="https://krogoco.se/jonkoping/kalender/",
        months=months,
    )
    with (
        patch.object(scraper, "_fetch_html", return_value=ROLLOVER_HTML),
        patch("krog_company_ics.krogoco_ics.date") as mock_date,
    ):
        mock_date.today.return_value = ROLLOVER_TODAY
        mock_date.side_effect = lambda *args, **kw: date(*args, **kw)
        return scraper.scrape_events()


def test_rollover_december_events_same_year():
    """December events should stay in the starting year."""
    events = _scrape_rollover(months=4)
    dec_events = [e for e in events if e.date.month == 12]
    assert len(dec_events) == 2
    assert all(e.date.year == 2025 for e in dec_events)


def test_rollover_january_events_next_year():
    """January events after December should roll over to the next year."""
    events = _scrape_rollover(months=4)
    jan_events = [e for e in events if e.date.month == 1]
    assert len(jan_events) == 2
    assert all(e.date.year == 2026 for e in jan_events)


def test_rollover_february_events_next_year():
    """February events after the rollover should also be in the next year."""
    events = _scrape_rollover(months=4)
    feb_events = [e for e in events if e.date.month == 2]
    assert len(feb_events) == 1
    assert feb_events[0].date == date(2026, 2, 14)
    assert feb_events[0].title == "Alla Hjärtans Dag"


def test_rollover_total_count():
    """All 6 events should be scraped across the year boundary."""
    events = _scrape_rollover(months=4)
    assert len(events) == 6


def test_rollover_chronological_order():
    """Events should be in chronological order across the year boundary."""
    events = _scrape_rollover(months=4)
    dates = [e.date for e in events]
    assert dates == sorted(dates)

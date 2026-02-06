"""KrogocoIcs class module.

Provides the :class:`KrogocoIcs` scraper and the :class:`CalendarEvent`
data class used to represent individual calendar entries.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from icalendar import Calendar, Event


@dataclass
class CalendarEvent:
    """A single scraped calendar event.

    :param date: The date of the event.
    :param title: The display title of the event.
    :param url: The full URL to the event detail page.
    :param all_day: ``True`` if the event has no specific start/end time.
    :param start_time: Start time as ``"HH:MM"`` string, or ``None`` for
        all-day events.
    :param end_time: End time as ``"HH:MM"`` string, or ``None`` if unknown.
    """

    date: date
    title: str
    url: str
    all_day: bool = True
    start_time: str | None = None
    end_time: str | None = None


def _last_day_of_month(d: date, months_ahead: int) -> date:
    """Return the last day of the month that is *months_ahead* after *d*.

    :param d: The reference date.
    :param months_ahead: Number of months to advance.
    :returns: The last day of the target month.
    """
    month = d.month + months_ahead
    year = d.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    # First day of the *next* month minus one day
    if month == 12:
        return date(year + 1, 1, 1) - timedelta(days=1)
    return date(year, month + 1, 1) - timedelta(days=1)


def _normalize_time(t: str) -> str:
    """Normalize a time string to ``HH:MM`` format.

    Converts dot-separated times (e.g. ``"17.00"``) to colon-separated
    (e.g. ``"17:00"``).

    :param t: A time string using either ``.`` or ``:`` as separator.
    :returns: The time string with ``:`` as separator.
    """
    return t.replace(".", ":")


def _parse_time_range(text: str) -> tuple[str | None, str | None, bool]:
    """Extract a time or time range from an event title.

    Handles several formats found on the Krog & Co calendar:

    * Full range: ``"19:00-23:00"`` or ``"19.00-23.00"``
    * Short range: ``"Kl.12-17"``
    * Single time: ``"Kl.17.00"`` or ``"Från 21:00"``
    * Time with age/end hint: ``"Kl.22.00, 23+"`` (interpreted as
      22:00–23:00)

    :param text: The event title text to parse.
    :returns: A tuple of ``(start_time, end_time, all_day)`` where times
        are ``"HH:MM"`` strings or ``None``, and *all_day* is ``True``
        when no time information was found.
    """
    # Range with full times: "12:00-17:00" or "12.00-17.00"
    m = re.search(r"(\d{1,2}[.:]\d{2})\s*[-–]\s*(\d{1,2}[.:]\d{2})", text)
    if m:
        return _normalize_time(m.group(1)), _normalize_time(m.group(2)), False

    # Range with short hours: "Kl.12-17"
    m = re.search(r"[Kk]l\.?\s*(\d{1,2})\s*[-–]\s*(\d{1,2})(?!\d|[.:/])", text)
    if m:
        return f"{int(m.group(1)):02d}:00", f"{int(m.group(2)):02d}:00", False

    # Time followed by "NN+" hint: "Kl.22.00, 23+" → 22:00-23:00
    m = re.search(r"(\d{1,2}[.:]\d{2})\s*,\s*(\d{1,2})\+", text)
    if m:
        return _normalize_time(m.group(1)), f"{int(m.group(2)):02d}:00", False

    # Single time with minutes: "Kl.17.00" or "Från 21:00"
    m = re.search(r"(\d{1,2}[.:]\d{2})", text)
    if m:
        return _normalize_time(m.group(1)), None, False

    return None, None, True


class KrogocoIcs:
    """Screen scrapes Krog & Co's calendar page and produces ICS output.

    The scraper walks the ``<h3>`` elements on the calendar page, which
    follow this structure:

    * Month headers (e.g. ``"februari"``)
    * Date lines (e.g. ``"torsdag 05/02"``)
    * Event links (``<a href="...">Event Title</a>``)

    Year rollover is detected automatically when the month number
    decreases (e.g. December → January).

    :param url: The URL to the Krog & Co calendar page.
    :param months: Number of months into the future to include.
    :param blacklist: Optional list of strings. Events whose title
        contains any of these strings (case-insensitive) will be
        excluded.

    Example usage::

        scraper = KrogocoIcs(
            url="https://krogoco.se/jonkoping/kalender/",
            months=2,
            blacklist=["HV71", "SHL"],
        )
        scraper.write_ics("calendar.ics")
    """

    BASE_URL = "https://krogoco.se"
    """Base URL used to resolve relative event links."""

    def __init__(
        self,
        url: str,
        months: int,
        blacklist: list[str] | None = None,
    ) -> None:
        self.url = url
        self.months = months
        self.blacklist = [b.casefold() for b in (blacklist or [])]

    # noinspection PyMethodMayBeStatic
    def _fetch_html(self, url: str) -> str:
        """Fetch and return the HTML content of a URL.

        :param url: The URL to fetch.
        :returns: The response body as a string.
        :raises requests.HTTPError: If the server returns an error status.
        """
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return resp.text

    def scrape_events(self) -> list[CalendarEvent]:
        """Scrape the calendar page and return a list of events.

        Parses the ``<h3>`` element structure of the calendar page,
        extracting dates and event links. Events in the past and events
        beyond the configured :attr:`months` horizon are excluded.
        Events matching the :attr:`blacklist` are also skipped.

        :returns: A list of :class:`CalendarEvent` instances in
            chronological order.
        """
        html = self._fetch_html(self.url)
        soup = BeautifulSoup(html, "html.parser")

        h3s = soup.find_all("h3")
        events: list[CalendarEvent] = []
        seen: set[tuple[date, str, str]] = set()

        today = date.today()
        horizon = _last_day_of_month(today, self.months)

        inferred_year = today.year
        prev_month: int | None = None
        current_date: date | None = None

        for h in h3s:
            txt = h.get_text(" ", True)  # type: ignore[call-overload]

            # Date lines look like: "lördag 31/01"
            m = re.search(r"\b(\d{2})/(\d{2})\b", txt)
            if m:
                dd = int(m.group(1))
                mm = int(m.group(2))

                # Detect year rollover (e.g. December -> January)
                if prev_month is not None and mm < prev_month:
                    inferred_year += 1

                prev_month = mm
                current_date = date(inferred_year, mm, dd)
                continue

            # Event lines: h3 containing an <a> link
            a = h.find("a", href=True)
            if a and current_date is not None:
                if current_date < today:
                    continue
                if current_date > horizon:
                    break

                title = a.get_text(" ", True)  # type: ignore[call-overload]

                # Skip blacklisted events (case-insensitive substring match)
                title_lower = title.casefold()
                if any(b in title_lower for b in self.blacklist):
                    continue

                url = a["href"]
                if url.startswith("/"):
                    url = urljoin(self.BASE_URL, url)

                # Skip duplicate events (same date, title and URL)
                key = (current_date, title, url)
                if key in seen:
                    continue
                seen.add(key)

                start_t, end_t, all_day = _parse_time_range(title)

                events.append(
                    CalendarEvent(
                        date=current_date,
                        title=title,
                        url=url,
                        all_day=all_day,
                        start_time=start_t,
                        end_time=end_t,
                    )
                )

        return events

    def _build_calendar(self) -> Calendar:
        """Scrape events and build an :class:`icalendar.Calendar` object.

        Each :class:`CalendarEvent` is converted to a ``VEVENT`` component:

        * **All-day events** use ``DATE`` values for ``DTSTART``/``DTEND``.
        * **Timed events** use ``DATETIME`` values. If only a start time is
          known, the end time defaults to midnight.
        * End times that fall before the start time are assumed to be past
          midnight and advanced by one day.

        :returns: A fully populated :class:`icalendar.Calendar`.
        """
        cal = Calendar()
        cal.add("prodid", "-//KrogCo//Calendar//EN")
        cal.add("version", "2.0")

        for ev in self.scrape_events():
            event = Event()
            event.add("summary", ev.title)
            event.add("url", ev.url)

            if ev.all_day:
                event.add("dtstart", ev.date)
                event.add("dtend", ev.date + timedelta(days=1))
            else:
                h, m = map(int, ev.start_time.split(":"))
                dtstart = datetime(ev.date.year, ev.date.month, ev.date.day, h, m)
                event.add("dtstart", dtstart)

                if ev.end_time:
                    h, m = map(int, ev.end_time.split(":"))
                    dtend = datetime(ev.date.year, ev.date.month, ev.date.day, h, m)
                    # Handle end time past midnight
                    if dtend <= dtstart:
                        dtend += timedelta(days=1)
                    event.add("dtend", dtend)
                else:
                    # No end time known — default to midnight
                    dtend = datetime(
                        ev.date.year, ev.date.month, ev.date.day
                    ) + timedelta(days=1)
                    event.add("dtend", dtend)

            cal.add_component(event)

        return cal

    def get_ics(self) -> str:
        """Scrape the calendar and return it as an ICS string.

        :returns: The full calendar in iCalendar (RFC 5545) format.
        """
        return self._build_calendar().to_ical().decode("utf-8")

    def write_ics(self, path: str | Path) -> None:
        """Scrape the calendar and write the ICS data to a file.

        :param path: Destination file path. Parent directories must exist.
        """
        Path(path).write_text(self.get_ics(), encoding="utf-8")

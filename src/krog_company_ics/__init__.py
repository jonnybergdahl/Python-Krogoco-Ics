"""Screen scrapes Krog & Co's calendar page to create an ICS file.

This package exposes two public symbols:

* :class:`KrogocoIcs` — the main scraper/ICS generator.
* :class:`CalendarEvent` — data class for individual events.
"""

from .krogoco_ics import CalendarEvent, KrogocoIcs

__all__ = ["CalendarEvent", "KrogocoIcs"]

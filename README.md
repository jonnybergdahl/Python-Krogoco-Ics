# krog-company-ics

A Python library that scrapes [Krog & Co](https://krogoco.se/) calendar pages
and converts them to iCalendar (ICS) files.

## Installation

```bash
pip install .
```

For development (includes pytest):

```bash
pip install -e ".[dev]"
```

## Usage

```python
from krog_company_ics import KrogocoIcs

scraper = KrogocoIcs(
    url="https://krogoco.se/jonkoping/kalender/",
    months=2,
)

# Get ICS as a string
ics_data = scraper.get_ics()

# Or write directly to a file
scraper.write_ics("krogoco.ics")
```

### Blacklist

You can filter out events by providing a blacklist of keywords.
Events whose title contains any of the keywords (case-insensitive) will
be excluded:

```python
scraper = KrogocoIcs(
    url="https://krogoco.se/jonkoping/kalender/",
    months=2,
    blacklist=["HV71", "SHL", "match"],
)
```

### Supported locations

The library works with any Krog & Co location that uses the same calendar
page structure:

- `https://krogoco.se/jonkoping/kalender/`
- `https://krogoco.se/halmstad/kalender/`

## Time format handling

Event times are extracted automatically from Swedish title formats:

| Format | Example | Parsed as |
|---|---|---|
| Full range | `12.00-16.00` | 12:00 - 16:00 |
| Short range | `Kl.12-17` | 12:00 - 17:00 |
| Single time | `Kl.17.00` or `Från 21:00` | 17:00 / 21:00 |
| Time with hint | `Kl.22.00, 23+` | 22:00 - 23:00 |
| No time | `Studentfest` | All-day event |

## Running tests

```bash
pytest
```

## License

MIT

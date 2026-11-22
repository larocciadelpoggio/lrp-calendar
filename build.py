#!/usr/bin/env python3
"""
Villa La Roccia del Poggio - price & availability builder.

Reads:
  * the price sheet: the Google Sheet published as CSV (secret PRICE_SHEET_URL),
    or the Excel file in data/ as a fallback. Columns are set in config.json:
    date (A), available 1/0 (B), minimum nights (D), website price (J = Vrbo input)
  * data/blocked.csv (extra dates you block yourself - optional)
  * the Airbnb and Vrbo iCal export links (config.json or env vars)

Column B of the sheet is the master. Nights marked 0 (closed) or W (direct booking)
are closed on the website AND sent to Airbnb and Vrbo through for-airbnb.ics /
for-vrbo.ics, together with the real bookings of the other platform. A platform's own
closed days are not passed on (they only show in the sheet's status columns).

Writes (to docs/, served by GitHub Pages):
  * availability.json  - nightly price, minimum stay and booked nights, read by the website calendar
  * calendar.ics       - every unavailable night (blocked + Airbnb + Vrbo)
  * for-airbnb.ics     - blocked + Vrbo bookings  -> import into Airbnb
  * for-vrbo.ics       - blocked + Airbnb bookings -> import into Vrbo

Usage:
  python build.py                 # build everything
  python build.py --no-fetch      # skip downloading Airbnb/Vrbo calendars

Environment variables PRICE_SHEET_URL / AIRBNB_ICAL_URL / VRBO_ICAL_URL
override config.json (use them as GitHub "secrets" so the links stay private).
"""
import csv
import datetime as dt
import io
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

try:
    import openpyxl
except ImportError:  # only needed for the Excel fallback
    openpyxl = None

ROOT = Path(__file__).resolve().parent
D = dt.date


def load_config():
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    feeds = cfg.setdefault("ical_feeds", {})
    for name in ("airbnb", "vrbo"):
        env = os.environ.get(f"{name.upper()}_ICAL_URL", "").strip()
        if env:
            feeds[name] = env
    return cfg


# ---------------------------------------------------------------- prices
# The price sheet (Google Sheet or Excel) has one row per date. Which column
# holds what is set in config.json -> "columns" (spreadsheet letters):
#   date  = the date                      (A)
#   open  = 1 / 0 - 0 closes the night     (B)
#   booked= W = direct booking (typed by you); A / V = Airbnb / Vrbo bookings,
#           written by the sheet's own script                       (C)
#   min   = minimum nights from that date (D)
#   price = website price per night       (L = input price on Vrbo)
# The row whose first cell is "add guest" gives the extra-guest fee
# (price column of that row).

def norm(v):
    return str(v).strip().lower() if v is not None else ""


def col_index(letter):
    n = 0
    for ch in letter.strip().upper():
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def to_number(v):
    """Numbers from Excel are floats; from a Google CSV they are text like '1.234,50' or '€ 124'."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace("€", "").replace("EUR", "").replace(" ", "").replace(" ", "").strip()
    if not s or s in ("-", "#N/A", "#VALUE!", "#REF!"):
        return None
    if "," in s and "." in s:          # 1.234,50 (it) or 1,234.50 (en)
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:                     # 124,5
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


MONTHS = {  # English and Italian month abbreviations, as Google Sheets shows them
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "gen": 1, "mag": 5, "giu": 6, "lug": 7, "ago": 8, "set": 9, "ott": 10, "dic": 12,
}


def to_date_words(s):
    """'Mon 01-Mar-27', 'lun 01-mar-27', '1 mar 2027' ... -> date (weekday ignored)."""
    parts = [p for p in re.split(r"[\s\-./,]+", s.lower()) if p]
    nums = [p for p in parts if p.isdigit()]
    # the month is the LAST word: the first one may be a weekday ('mar' = martedì and marzo)
    mon = next((MONTHS[p[:3]] for p in reversed(parts) if p[:3] in MONTHS and not p.isdigit()), None)
    if mon is None or len(nums) < 2:
        return None
    day, year = int(nums[0]), int(nums[1])
    if year < 100:
        year += 2000
    try:
        return dt.date(year, mon, day)
    except ValueError:
        return None


def to_date(v, day_first=True):
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    s = str(v or "").strip()
    if not s or not any(ch.isdigit() for ch in s):
        return None
    if any(ch.isalpha() for ch in s):
        return to_date_words(s)
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return dt.datetime.strptime(s[:10], fmt).date()
        except ValueError:
            pass
    fmts = ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%m/%d/%Y", "%d/%m/%y") if day_first else \
           ("%m/%d/%Y", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%m/%d/%y")
    for fmt in fmts:
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def parse_price_rows(rows, cfg, label):
    """rows: list of lists of cell values. Returns (days, closed, extra_fee)."""
    cols = cfg.get("columns", {})
    c_date = col_index(cols.get("date", "A"))
    c_open = col_index(cols.get("open", "B"))
    c_min = col_index(cols.get("min", "D"))
    c_booked = col_index(cols.get("booked", "C"))
    auto_codes = {norm(w) for w in cfg.get("platform_booking_codes", ["A", "V"])}
    c_price = col_index(cols.get("price", "J"))
    extra_label = norm(cfg.get("extra_guest_label", "add guest"))
    closed_words = {norm(w) for w in cfg.get("closed_values", ["n", "no", "closed", "chiuso", "0", "false"])}
    default_min = int(cfg.get("default_min_nights", 3))
    day_first = cfg.get("day_first", True)

    def cell(r, i):
        return r[i] if i < len(r) else None

    days, closed, direct, extra_fee = {}, set(), set(), None
    for r in rows:
        if not r:
            continue
        if norm(cell(r, 0)) == extra_label:
            fee = to_number(cell(r, c_price))
            if fee is not None:
                extra_fee = fee
            continue
        day = to_date(cell(r, c_date), day_first)
        if day is None:
            continue
        bk = norm(cell(r, c_booked))
        if bk and bk not in auto_codes:      # W (or any note) = direct booking
            direct.add(day)
        if norm(cell(r, c_open)) in closed_words:
            closed.add(day)
            continue
        price = to_number(cell(r, c_price))
        if not price:              # empty or 0 = no price yet = not bookable on the website
            continue
        mn = to_number(cell(r, c_min))
        days[day] = {"p": round(price, 2), "m": max(1, int(mn)) if mn else default_min}
    print(f"  {label}: {len(days)} priced nights, {len(closed)} closed nights, {len(direct)} direct-booking nights")
    return days, closed, direct, extra_fee


def fetch_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (LRP calendar sync)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8-sig", errors="replace")


def read_prices(cfg):
    """Return (days, closed_nights, extra_guest_fee).

    Source 1: PRICE_SHEET_URL (GitHub secret) = the Google Sheet tab published
              as CSV. Several links can be given, separated by spaces/new lines
              (e.g. one tab per year).
    Source 2 (fallback): the Excel file in config "price_file".
    """
    days, closed, direct, extra_fee = {}, set(), set(), None
    urls = (os.environ.get("PRICE_SHEET_URL") or cfg.get("price_sheet_url") or "").split()
    cache = ROOT / "data" / ".cache_prices.json"
    if urls:
        try:
            for i, url in enumerate(urls, 1):
                rows = list(csv.reader(io.StringIO(fetch_text(url))))
                d, c, b, x = parse_price_rows(rows, cfg, f"Google Sheet {i}")
                days.update(d)
                closed |= c
                direct |= b
                extra_fee = x if x is not None else extra_fee
            if not days and not closed:
                raise ValueError("the sheet contains no dates - check the published link")
            cache.write_text(json.dumps({"days": {k.isoformat(): v for k, v in days.items()},
                                         "closed": sorted(k.isoformat() for k in closed),
                                         "direct": sorted(k.isoformat() for k in direct),
                                         "extra": extra_fee}))
            return days, closed, direct, extra_fee
        except Exception as ex:
            print(f"  WARNING: could not read the Google Sheet ({ex})")
            if cache.exists():
                c = json.loads(cache.read_text())
                print("  using the last copy that was read successfully")
                return ({D.fromisoformat(k): v for k, v in c["days"].items()},
                        {D.fromisoformat(k) for k in c["closed"]},
                        {D.fromisoformat(k) for k in c.get("direct", [])}, c["extra"])
            print("  falling back to the Excel file")

    path = ROOT / cfg.get("price_file", "")
    if not path.is_file():
        sys.exit("No price source: set the PRICE_SHEET_URL secret or put the Excel file in data/")
    if openpyxl is None:
        sys.exit("Missing package: run  pip install openpyxl")
    wb = openpyxl.load_workbook(path, data_only=True)
    for ws in wb.worksheets:
        d, c, b, x = parse_price_rows([list(r) for r in ws.iter_rows(values_only=True)], cfg, f"Excel sheet '{ws.title}'")
        days.update(d)
        closed |= c
        direct |= b
        extra_fee = x if x is not None else extra_fee
    return days, closed, direct, extra_fee


# ---------------------------------------------------------------- blocked
def parse_date(s):
    return D.fromisoformat(s.strip()[:10])


def read_blocked(cfg):
    path = ROOT / cfg["blocked_file"]
    out = []
    if not path.exists():
        return out
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.lower().startswith("from"):
                continue
            parts = next(csv.reader([line]))
            if len(parts) < 2:
                continue
            start, end = parse_date(parts[0]), parse_date(parts[1])
            if end <= start:  # single night given as from=to
                end = start + dt.timedelta(days=1)
            out.append((start, end, (parts[2] if len(parts) > 2 else "Blocked").strip() or "Blocked"))
    return out


# ---------------------------------------------------------------- iCal
def unfold(text):
    lines = []
    for raw in text.replace("\r\n", "\n").split("\n"):
        if raw.startswith((" ", "\t")) and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def parse_ics(text):
    events, cur = [], None
    for line in unfold(text):
        if line == "BEGIN:VEVENT":
            cur = {}
        elif line == "END:VEVENT" and cur is not None:
            if "start" in cur:
                end = cur.get("end") or cur["start"] + dt.timedelta(days=1)
                events.append((cur["start"], end, cur.get("summary", "Booked")))
            cur = None
        elif cur is not None and ":" in line:
            key, val = line.split(":", 1)
            name = key.split(";")[0].upper()
            if name in ("DTSTART", "DTEND"):
                v = val.strip()
                d = D(int(v[0:4]), int(v[4:6]), int(v[6:8]))
                cur["start" if name == "DTSTART" else "end"] = d
            elif name == "SUMMARY":
                cur["summary"] = val.strip()
    return events


def nights(start, end):
    d = start
    while d < end:
        yield d
        d += dt.timedelta(days=1)


def write_ics(path, events, name):
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//La Roccia del Poggio//Calendar//EN",
           "CALSCALE:GREGORIAN", "METHOD:PUBLISH", f"X-WR-CALNAME:{name}"]
    for i, (s, e, summary, src) in enumerate(sorted(events)):
        out += ["BEGIN:VEVENT",
                f"UID:{s:%Y%m%d}-{e:%Y%m%d}-{src}-{i}@larocciadelpoggio.com",
                f"DTSTAMP:{stamp}",
                f"DTSTART;VALUE=DATE:{s:%Y%m%d}",
                f"DTEND;VALUE=DATE:{e:%Y%m%d}",
                "SUMMARY:Not available",
                "END:VEVENT"]
    out.append("END:VCALENDAR")
    path.write_text("\r\n".join(out) + "\r\n", encoding="utf-8")


def is_booking(summary):
    """True for a real reservation, False for a block.
    Airbnb exports reservations as 'Reserved' and blocks as 'Airbnb (Not available)'."""
    s = (summary or "").lower()
    if any(w in s for w in ("not available", "unavailable", "blocked", "bloccat", "non disponibile", "closed")):
        return False
    return any(w in s for w in ("reserv", "book", "prenot", "riserv"))


def merge_ranges(events):
    """Merge overlapping/adjacent (start, end) ranges."""
    merged = []
    for s, e in sorted(events):
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return [(s, e) for s, e in merged]


# ---------------------------------------------------------------- main
def main():
    fetch = "--no-fetch" not in sys.argv
    cfg = load_config()
    out_dir = ROOT / cfg.get("output_dir", "docs")
    out_dir.mkdir(exist_ok=True)

    print("Reading prices ...")
    days, closed, direct, extra_fee = read_prices(cfg)
    if extra_fee is None:
        extra_fee = 0
    print(f"  extra guest fee: {extra_fee}")

    print("Reading blocked dates ...")
    blocked = read_blocked(cfg)
    print(f"  {len(blocked)} blocked period(s) in blocked.csv")

    # nights marked closed (0) in the sheet, merged into periods
    closed_periods = merge_ranges([(d, d + dt.timedelta(days=1)) for d in closed])
    print(f"  {len(closed_periods)} closed period(s) from the price sheet")

    direct_periods = merge_ranges([(d, d + dt.timedelta(days=1)) for d in direct])
    print(f"  {len(direct_periods)} direct booking(s) (W) from the price sheet")

    channel_events = {"blocked": [(s, e, note) for s, e, note in blocked] +
                                 [(s, e, "Closed") for s, e in closed_periods] +
                                 [(s, e, "Booked (direct)") for s, e in direct_periods]}
    for name, url in cfg.get("ical_feeds", {}).items():
        if not url:
            print(f"  {name}: no iCal link configured")
            continue
        if not fetch:
            print(f"  {name}: skipped (--no-fetch)")
            continue
        try:
            evs = parse_ics(fetch_text(url))
            channel_events[name] = evs
            print(f"  {name}: {len(evs)} event(s)")
        except Exception as ex:  # keep last good data if a feed fails
            print(f"  WARNING {name}: could not download calendar ({ex})")
            prev = ROOT / "data" / f".cache_{name}.json"
            if prev.exists():
                channel_events[name] = [(D.fromisoformat(a), D.fromisoformat(b), c)
                                        for a, b, c in json.loads(prev.read_text())]
                print(f"  {name}: using last saved copy")
        else:
            (ROOT / "data" / f".cache_{name}.json").write_text(
                json.dumps([(s.isoformat(), e.isoformat(), c) for s, e, c in evs]))
            kinds = {}
            for _, _, c in evs:
                kinds[c] = kinds.get(c, 0) + 1
            print(f"    event titles: {kinds}")

    today = D.today()
    # Column B of the sheet is the master: the website and the feeds sent to Airbnb/Vrbo use
    # only our own closures (B = 0, W, blocked.csv) and real BOOKINGS on Airbnb/Vrbo -
    # never a platform's own closed days (those only show in the sheet's status columns).
    def bookings_only(evs):
        return [(s, e, note) for s, e, note in evs if is_booking(note)]

    unavailable = set()
    for src, evs in channel_events.items():
        for s, e, _ in (evs if src == "blocked" else bookings_only(evs)):
            for n in nights(s, e):
                if n >= today:
                    unavailable.add(n)

    data = {
        "generated": dt.datetime.now().replace(microsecond=0).isoformat(),
        "currency": cfg.get("currency", "EUR"),
        "extraGuestFee": extra_fee,
        "baseGuests": cfg.get("base_guests", 6),
        "maxGuests": cfg.get("max_guests", 13),
        "email": cfg.get("booking_email", ""),
        "property": cfg.get("property_name", ""),
        "notes": {"en": cfg.get("fees_note_en", ""), "it": cfg.get("fees_note_it", "")},
        "days": {d.isoformat(): v for d, v in sorted(days.items()) if d >= today - dt.timedelta(days=1)},
        "unavailable": sorted(d.isoformat() for d in unavailable),
    }
    (out_dir / "availability.json").write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")

    def booked_on(src):
        return {n for s, e, note in channel_events.get(src, []) if is_booking(note) for n in nights(s, e)}

    def evs_for(*sources, skip=frozenset()):
        """Events from the given sources; nights in `skip` are cut out (split into pieces)."""
        rows = []
        for src in sources:
            evs = channel_events.get(src, [])
            for s, e, note in (evs if src == "blocked" else bookings_only(evs)):
                if e <= today:
                    continue
                keep = [n for n in nights(s, e) if n not in skip]
                for a, b in merge_ranges([(n, n + dt.timedelta(days=1)) for n in keep]):
                    rows.append((a, b, note, src))
        return rows

    all_src = list(channel_events)
    write_ics(out_dir / "calendar.ics", evs_for(*all_src), "La Roccia del Poggio - all")
    # Each platform gets everything except its own feed - and not the nights that are already
    # booked on it: otherwise its own booking, echoed back by the other platform as a block,
    # would come back to it and could stay blocked after a cancellation.
    write_ics(out_dir / "for-airbnb.ics", evs_for(*[s for s in all_src if s != "airbnb"], skip=booked_on("airbnb")),
              "La Roccia del Poggio - for Airbnb")
    write_ics(out_dir / "for-vrbo.ics", evs_for(*[s for s in all_src if s != "vrbo"], skip=booked_on("vrbo")),
              "La Roccia del Poggio - for Vrbo")

    # per-night status on each platform -> docs/status.csv, read by the Google Sheet:
    #   tab "Status" (columns F and J of the price sheet) and the sheet script that
    #   writes A / V into the Booked column.  Only nights that are not open are listed.
    #   Line format: day number, Airbnb status, Vrbo status, date   (status = Booked / Closed)
    serial0 = D(1899, 12, 30)   # spreadsheet day numbers: match the sheet whatever its language
    status = {}
    for i, src in enumerate(("airbnb", "vrbo")):
        for s, e, summary in channel_events.get(src, []):
            st = "Booked" if is_booking(summary) else "Closed"
            for n in nights(s, e):
                row = status.setdefault(n, ["", ""])
                if row[i] != "Booked":
                    row[i] = st
    lines = [f"{(d - serial0).days},{a or 'Open'},{v or 'Open'},{d.isoformat()}\n" for d, (a, v) in sorted(status.items())]
    (out_dir / "status.csv").write_text("".join(lines) or "0,Open,Open,1899-12-30\n", encoding="utf-8")
    nb = sum(1 for a, v in status.values() if "Booked" in (a, v))
    print(f"  status.csv: {len(status)} nights not open on Airbnb/Vrbo, {nb} of them booked")

    priced = [d for d in days if d >= today]
    print(f"Done: {len(priced)} future priced nights, {len(unavailable)} unavailable nights")
    if priced:
        print(f"  prices from {min(priced)} to {max(priced)}")
    print(f"  output in {out_dir}")


if __name__ == "__main__":
    main()

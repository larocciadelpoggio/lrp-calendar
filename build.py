#!/usr/bin/env python3
"""
Villa La Roccia del Poggio - price & availability builder.

Reads:
  * the price list Excel (one sheet per year, columns "min days" and "direct")
  * data/blocked.csv (dates you block yourself)
  * the Airbnb and Vrbo iCal export links (config.json or env vars)

Writes (to docs/, served by GitHub Pages):
  * availability.json  - nightly price, minimum stay and booked nights, read by the website calendar
  * calendar.ics       - every unavailable night (blocked + Airbnb + Vrbo)
  * for-airbnb.ics     - blocked + Vrbo bookings  -> import into Airbnb
  * for-vrbo.ics       - blocked + Airbnb bookings -> import into Vrbo

Usage:
  python build.py                 # build everything
  python build.py --no-fetch      # skip downloading Airbnb/Vrbo calendars

Environment variables AIRBNB_ICAL_URL / VRBO_ICAL_URL override config.json
(use them as GitHub "secrets" so the private links are not public).
"""
import csv
import datetime as dt
import json
import os
import sys
import urllib.request
from pathlib import Path

try:
    import openpyxl
except ImportError:
    sys.exit("Missing package: run  pip install openpyxl")

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
def norm(v):
    return str(v).strip().lower() if v is not None else ""


def read_prices(cfg):
    """Return ({date: {"p": price, "m": min_nights}}, extra_guest_fee)."""
    path = ROOT / cfg["price_file"]
    wb = openpyxl.load_workbook(path, data_only=True)
    price_col_name = norm(cfg.get("price_column", "direct"))
    min_col_name = norm(cfg.get("min_nights_column", "min days"))
    extra_label = norm(cfg.get("extra_guest_label", "add guest"))
    days, extra_fee = {}, None

    for ws in wb.worksheets:
        rows = list(ws.iter_rows(values_only=True))
        # locate the header row containing the price column name
        price_col = min_col = None
        for r in rows[:15]:
            cells = [norm(c) for c in r]
            if price_col_name in cells:
                price_col = cells.index(price_col_name)
                if min_col_name in cells:
                    min_col = cells.index(min_col_name)
                break
        if price_col is None:
            print(f"  sheet '{ws.title}': no '{price_col_name}' column, skipped")
            continue
        if min_col is None:
            min_col = 1
        n = 0
        for r in rows:
            first = r[0] if r else None
            if norm(first) == extra_label and price_col < len(r) and r[price_col] is not None:
                extra_fee = float(r[price_col])
                continue
            if isinstance(first, (dt.datetime, dt.date)):
                day = first.date() if isinstance(first, dt.datetime) else first
                price = r[price_col] if price_col < len(r) else None
                if price in (None, ""):
                    continue
                mn = r[min_col] if min_col < len(r) else None
                try:
                    mn = int(mn) if mn not in (None, "") else int(cfg.get("default_min_nights", 1))
                except (TypeError, ValueError):
                    mn = int(cfg.get("default_min_nights", 1))
                days[day] = {"p": round(float(price), 2), "m": max(1, mn)}
                n += 1
        print(f"  sheet '{ws.title}': {n} priced nights")
    return days, extra_fee


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


def fetch_ics(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (LRP calendar sync)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


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
    days, extra_fee = read_prices(cfg)
    if extra_fee is None:
        extra_fee = 0
    print(f"  extra guest fee: {extra_fee}")

    print("Reading blocked dates ...")
    blocked = read_blocked(cfg)
    print(f"  {len(blocked)} blocked period(s)")

    channel_events = {"blocked": [(s, e, note) for s, e, note in blocked]}
    for name, url in cfg.get("ical_feeds", {}).items():
        if not url:
            print(f"  {name}: no iCal link configured")
            continue
        if not fetch:
            print(f"  {name}: skipped (--no-fetch)")
            continue
        try:
            evs = parse_ics(fetch_ics(url))
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
                json.dumps([(s.isoformat(), e.isoformat(), "Booked") for s, e, c in evs]))

    today = D.today()
    unavailable = set()
    for evs in channel_events.values():
        for s, e, _ in evs:
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

    def evs_for(*sources):
        rows = []
        for src in sources:
            for s, e, note in channel_events.get(src, []):
                if e > today:
                    rows.append((s, e, note, src))
        return rows

    all_src = list(channel_events)
    write_ics(out_dir / "calendar.ics", evs_for(*all_src), "La Roccia del Poggio - all")
    write_ics(out_dir / "for-airbnb.ics", evs_for(*[s for s in all_src if s != "airbnb"]),
              "La Roccia del Poggio - for Airbnb")
    write_ics(out_dir / "for-vrbo.ics", evs_for(*[s for s in all_src if s != "vrbo"]),
              "La Roccia del Poggio - for Vrbo")

    priced = [d for d in days if d >= today]
    print(f"Done: {len(priced)} future priced nights, {len(unavailable)} unavailable nights")
    if priced:
        print(f"  prices from {min(priced)} to {max(priced)}")
    print(f"  output in {out_dir}")


if __name__ == "__main__":
    main()

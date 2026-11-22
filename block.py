#!/usr/bin/env python3
"""
Block or unblock dates on your own calendar (data/blocked.csv).

  python block.py add 2026-08-01 2026-08-08 "Family holiday"   # nights 1-7 Aug blocked, 8 Aug free
  python block.py add 2026-12-24                               # one night
  python block.py remove 2026-08-01                            # remove the period starting that day
  python block.py list

After changing, run  python build.py  (or upload blocked.csv to GitHub; the site updates itself).
"""
import csv
import datetime as dt
import sys
from pathlib import Path

PATH = Path(__file__).resolve().parent / "data" / "blocked.csv"
HEADER = ["# One line per blocked period. \"from\" = first night blocked, \"to\" = check-out day (that night stays free).",
          "# Dates as YYYY-MM-DD. Lines starting with # are ignored."]


def load():
    rows = []
    if PATH.exists():
        for line in PATH.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.startswith("#") and not line.lower().startswith("from"):
                rows.append(next(csv.reader([line])))
    return rows


def save(rows):
    rows.sort(key=lambda r: r[0])
    with PATH.open("w", encoding="utf-8", newline="") as f:
        f.write("from,to,note\n" + "\n".join(HEADER) + "\n")
        w = csv.writer(f)
        for r in rows:
            w.writerow(r)


def main(argv):
    if not argv or argv[0] not in ("add", "remove", "list"):
        print(__doc__)
        return
    rows = load()
    if argv[0] == "list":
        for r in rows:
            print(" -> ".join(r[:2]), "|", r[2] if len(r) > 2 else "")
        return
    start = dt.date.fromisoformat(argv[1])
    if argv[0] == "add":
        end = dt.date.fromisoformat(argv[2]) if len(argv) > 2 and argv[2][:4].isdigit() else start + dt.timedelta(days=1)
        note = argv[3] if len(argv) > 3 else (argv[2] if len(argv) > 2 and not argv[2][:4].isdigit() else "Blocked")
        if end <= start:
            sys.exit("'to' must be after 'from'")
        rows.append([start.isoformat(), end.isoformat(), note])
        print(f"Blocked nights {start} to {end - dt.timedelta(days=1)} ({note})")
    else:
        before = len(rows)
        rows = [r for r in rows if r[0] != start.isoformat()]
        print(f"Removed {before - len(rows)} period(s)")
    save(rows)


if __name__ == "__main__":
    main(sys.argv[1:])

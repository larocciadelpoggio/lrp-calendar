# La Roccia del Poggio – prices & availability calendar

The system takes three inputs:

- your price Excel: the **direct** column gives the nightly price, **min days** gives the minimum stay, and the **add guest** row gives the fee per extra guest per night above 6;
- your own blocked dates (`data/blocked.csv`);
- the Airbnb and Vrbo calendars.

From these it builds a booking calendar for the website. The calendar shows:

- the nightly price for each date;
- the minimum stay;
- which nights are booked;
- a total price for the dates and number of guests the visitor picks.

Visitors send a booking request with a "Request booking by email" button that opens a pre-filled email. The system also builds calendar feeds, so Airbnb and Vrbo can block each other's bookings and your own blocked dates.

GitHub runs everything for free. It re-reads Airbnb and Vrbo every 3 hours, and it rebuilds the calendar straight away each time you upload a new Excel or blocked-dates file.

```
Lista_prezzi_website.xlsx ─┐
data/blocked.csv ──────────┼─> build.py ─> docs/availability.json  (website calendar)
Airbnb iCal ───────────────┤               docs/for-airbnb.ics     (import into Airbnb)
Vrbo iCal ─────────────────┘               docs/for-vrbo.ics       (import into Vrbo)
                                           docs/calendar.ics       (everything, for your phone)
```

---

## 1. One-time setup (about 20 minutes)

### 1a. Put the project on GitHub
1. Create a free account at https://github.com (if you don't have one).
2. Click **+ → New repository**. Fill it in as follows:
   - Name: `lrp-calendar`.
   - Visibility: **Public**. GitHub Pages is only free for public repos. This means the Excel is publicly readable, Airbnb/Vrbo columns included. If you don't want that, delete those two columns before uploading; only "min days" and "direct" are needed.
   - Click **Create**.
3. On the new repo page, click **uploading an existing file**. Drag in **all the contents** of this folder: `build.py`, `block.py`, `config.json`, `README.md`, and the `data`, `docs` and `.github` folders. Then click **Commit changes**.
   - The `.github` folder is hidden in Windows Explorer. If it doesn't upload, create it on GitHub instead: **Add file → Create new file**, type the name `.github/workflows/update.yml`, and paste the content of that file.

### 1b. Turn on the web page
**Settings → Pages**. Under **Source**, choose *Deploy from a branch*, then the branch `main` and the folder `/docs`, and click **Save**.

About a minute later the calendar is live at
`https://YOUR-USERNAME.github.io/lrp-calendar/`.

### 1c. Allow the automatic updates
Go to **Settings → Actions → General → Workflow permissions**, choose **Read and write permissions**, and click **Save**.

### 1d. Connect Airbnb and Vrbo
**Get the export links:**

- **Airbnb:** Calendar → Availability → *Connect calendars* (or *Sync calendars*) → **Export calendar**. Copy the link.
- **Vrbo:** Calendar → Import/Export → **Export**. Copy the link.

**Store them as secrets.** These links are private, so they don't go in config.json. In the repo, open **Settings → Secrets and variables → Actions → New repository secret** and add:

- `AIRBNB_ICAL_URL` = the Airbnb link
- `VRBO_ICAL_URL` = the Vrbo link

Then go to **Actions → Update calendar → Run workflow** to run it once.

**Import the merged calendars into the platforms:**

- **Airbnb:** *Import calendar*. Link: `https://YOUR-USERNAME.github.io/lrp-calendar/for-airbnb.ics`. Name: "Direct + Vrbo".
- **Vrbo:** *Import*. Link: `https://YOUR-USERNAME.github.io/lrp-calendar/for-vrbo.ics`. Name: "Direct + Airbnb".

Each platform only receives the *other* bookings, so bookings never bounce back and forth between them.

Airbnb and Vrbo refresh imported calendars every few hours. There is always a small window in which a double booking is possible.

### 1e. Put the calendar on the website (Hostinger)
In the Hostinger builder, open the page where you want the calendar (for example Contacts, or a new "Prices & availability" section). Then:

1. Add **Elements → Embed code**.
2. Paste the code below.
3. Repeat on the Italian page with `lang=it`.

```html
<iframe src="https://YOUR-USERNAME.github.io/lrp-calendar/widget.html?lang=en"
        style="width:100%;height:760px;border:0" loading="lazy"
        title="Prices and availability"></iframe>
```

If the calendar looks cut off on phones, set the embed height to about 1000px on mobile.

---

## 2. Everyday use

### Update prices
Edit your Excel, keeping the same layout: dates in column A, plus the **min days** and **direct** columns and the **add guest** row. You can add a sheet for each new year (2027, …); every sheet is read.

On GitHub, open the `data` folder, then **Add file → Upload files**. Upload it with **exactly the same name**, `Lista_prezzi_website.xlsx`, and click **Commit**. The website updates in about 1 minute.

### Block dates (your own use, maintenance, direct bookings)
On GitHub, open `data/blocked.csv`, click the ✏️ pencil, add a line and click **Commit changes**:

```
2026-08-01,2026-08-08,Family holiday
```

"from" is the first night that is blocked. "to" is the check-out day: that night stays free. The example above blocks the nights of 1–7 August.

The note is private. It never shows on the website or in the calendars, which only show "Not available".

To unblock dates, delete the line.

### Check sync
Open the **Actions** tab. Every run is listed there with a green tick or a red cross. Click a run to see how many bookings were read from Airbnb and Vrbo.

---

## 3. Optional: work from your PC with Python

Install Python (https://python.org), then run `pip install openpyxl`. Then:

```
python block.py add 2026-08-01 2026-08-08 "Family holiday"
python block.py add 2026-12-24                 # one night
python block.py remove 2026-08-01
python block.py list
python build.py --no-fetch                     # rebuild and preview locally
```

To preview, open `docs/index.html` after running `python -m http.server` in this folder.

`update.bat` rebuilds the calendar and pushes your changes to GitHub. It needs Git installed and the repo cloned with GitHub Desktop.

---

## 4. Settings (`config.json`)

| key | meaning |
|---|---|
| `price_column` / `min_nights_column` | Excel column headers to read (`direct`, `min days`) |
| `extra_guest_label` | label of the row holding the extra-guest fee (`add guest`) |
| `base_guests` / `max_guests` | guests included in the price (6) / maximum guests (13) |
| `default_min_nights` | used when a date has no "min days" value |
| `booking_email` | where booking requests are sent |
| `fees_note_en` / `fees_note_it` | note shown under the total |

## How the rules work
- **Prices.** The price for a stay is the sum of the "direct" price of each night. On top of that, each guest above 6 costs the "add guest" fee per night.
- **Minimum stay.** The minimum stay is the "min days" value of the **check-in** date.
- **Unavailable dates.** Dates with no price in the Excel can't be booked. The same goes for nights that are blocked or booked on Airbnb or Vrbo. A booked night can still be chosen as a check-out day.

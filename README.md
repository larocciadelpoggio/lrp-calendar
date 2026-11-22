# La Roccia del Poggio – prices & availability calendar

The system takes three inputs:

- your **price sheet** in Google Sheets (`house_rental_price`, on larocciadelpoggio@gmail.com, tab **Prices**):

  | A | B | C | D | E | F–I Airbnb | J–M Vrbo |
  |---|---|---|---|---|---|---|
  | Date | Available 1/0 | Booked W/A/V | Min stay | Input price (yellow) | Status · Net · **Input on Airbnb** (pink) · Client | Status · Net · **Input on Vrbo** (blue) · Client |

  - **B** is yours: 0 closes a night on the website, Airbnb and Vrbo.
  - **C**: type **W** for a website/direct booking (blocks all three). **A** (Airbnb) and **V** (Vrbo) are written by the sheet's script every hour; it never overwrites what you type.
  - **F / J** (status on Airbnb / Vrbo: Open, Closed, Booked) fill in by themselves from `status.csv`, through the tab **Status**.
  - The website price is column **L** (the Vrbo input, before Vrbo's guest markup).
- optional extra blocked dates (`data/blocked.csv`);
- the Airbnb and Vrbo calendars.

From these it builds a booking calendar for the website. Prices are **not** shown per night: the visitor picks dates and guests, then sees the total and a "Request booking by email" button.

Nights marked **0** in the sheet are closed on the website **and** on Airbnb and Vrbo, through the calendar links. Airbnb and Vrbo **prices and minimum stays are not synced**, because their calendar links only carry blocked dates; those you set on each platform.

GitHub runs everything for free and re-reads the sheet, Airbnb and Vrbo every hour.

```
Google Sheet (A-E,L) ──┐
data/blocked.csv ──────┼─> build.py ─> docs/availability.json  (website calendar)
Airbnb iCal ───────────┤               docs/for-airbnb.ics     (import into Airbnb)
Vrbo iCal ─────────────┘               docs/for-vrbo.ics       (import into Vrbo)
                                       docs/calendar.ics       (everything, for your phone)
```

---

## 1. One-time setup (about 20 minutes)

### 1a. Put the project on GitHub
1. Create a free account at https://github.com (if you don't have one).
2. Click **+ → New repository**. Fill it in as follows:
   - Name: `lrp-calendar`.
   - Visibility: **Public**. GitHub Pages is only free for public repos, so don't put your price Excel in the repo: the prices live in the private Google Sheet.
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

### Update prices, minimum stays, open/closed days
Edit the Google Sheet: price in the yellow column E, minimum stay in D, **1**/**0** in B, **W** in C for a direct booking. To add dates, copy the last row down. The website and the Airbnb/Vrbo blocked dates follow within about an hour. To update at once: **Actions → Update calendar → Run workflow**.

Then copy the pink column H to Airbnb and the blue column L to Vrbo, with the minimum stays, yourself, since the calendar links can't carry them.

### Sheet script (one-time)
In the Google Sheet: **Extensions → Apps Script**, delete what is there, paste `google-sheet-script.gs`, click 💾 Save, choose **setup** in the function list, click **Run** and allow access. It then fills A/V in column C every hour.

### Google Sheet link (one-time)
In the sheet: **File → Share → Publish to web**, choose the tab **Prices** and **Comma-separated values (.csv)**, then **Publish**. Copy the link and save it in GitHub as the secret `PRICE_SHEET_URL` (**Settings → Secrets and variables → Actions**). For a second tab (e.g. a new year), publish it too and put both links in the secret, separated by a space.

### Extra blocked dates (optional)
You can also block dates in `data/blocked.csv` (✏️ pencil on GitHub, one line per period):

```
2026-08-01,2026-08-08,Family holiday
```

"from" is the first night that is blocked. "to" is the check-out day: that night stays free. The note is private.

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
| `columns` | sheet columns for date (A), available (B), booked (C), minimum stay (D), website price (L) |
| `closed_values` | what counts as closed in the Available column (0, N, No, Closed, Chiuso) |
| `extra_guest_label` | label of the row holding the extra-guest fee (`add guest`) |
| `base_guests` / `max_guests` | guests included in the price (6) / maximum guests (13) |
| `default_min_nights` | used when a date has no minimum stay |
| `booking_email` | where booking requests are sent |
| `fees_note_en` / `fees_note_it` | note shown under the total |
| `price_file` | Excel used only if the Google Sheet can't be read and no saved copy exists |

## How the rules work
- **Prices.** The price for a stay is the sum of the column L price of each night. On top of that, each guest above 6 costs the "add guest" fee per night.
- **Minimum stay.** The minimum stay is the "min days" value of the **check-in** date.
- **Unavailable dates.** Nights marked 0, or with no price, can't be booked. The same goes for nights blocked in blocked.csv or booked on Airbnb or Vrbo. Only nights marked 0 (and blocked.csv) are sent to Airbnb and Vrbo. A booked night can still be chosen as a check-out day.

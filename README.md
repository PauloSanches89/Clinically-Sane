# Clinically Sane

A map of Cape Town public clinic queues. People at a clinic report how long they have waited and how many people are in front of them. The map turns those reports into a live pin for today and a running average for each clinic.

Live site: https://clinicallysane.vercel.app

## What it does

The home screen is a Leaflet map of the clinics in `data/clinics.json`. With nothing selected, a list of clinics sits on the left. Choosing a clinic opens its panel and hides that list until you close the panel.

- **Near me** asks the browser for the device location and opens the closest clinic inside Cape Town. The coordinates stay in the page. They are not sent to the API.
- **Search** looks up a Cape Town place and moves the map there.
- **Report** asks for minutes waited, people in line, or both. Zero counts. The visit is either still waiting or already seen. A short note is optional and is checked in the app before it is stored.
- **Live pin** uses people who are still waiting, and only reports from the current day in South African Standard Time. The pin shows the median. When three or more reports include both numbers, a report that sits more than 50% away from both medians is marked as an outlier.
- **Averages** use visits that have already been seen. The all-time figure and the last seven days are weighted by how many reports each day contributed. A report can update only the wait, only the line length, or both.
- **Closed today** is a flag that the clinic has sent people away. Two different reporters on the same day confirm it.
- Reports and the live pin expire at midnight SAST. The averages remain.
- The same visitor can file one report and one closure flag per clinic every 15 minutes. The visitor IP is hashed and the raw address is not stored.

## Tech stack

| Layer | Choice |
| --- | --- |
| API | Python 3, FastAPI, served by Uvicorn |
| Map | React 18, Vite, Leaflet, React Leaflet |
| Clinic list | `data/clinics.json`, bundled with the API |
| Live day | `today.json`: raw reports, closure flags, and rate-limit timestamps for the current SAST date |
| History | `stats.json`: per-clinic sums, counts, the last seven daily buckets, and confirmed closure days |
| Hosted storage | Private Vercel Blob, one object for each file |
| Local storage | The same two JSON files under `data/` when no Blob store is configured |
| Notes | Reviewed in-process in `app/moderate.py`. No external model is called |
| Place search | OpenStreetMap Nominatim, cached in the API process |

## Deployment

The GitHub repository is connected to a Vercel project. A push to `main` builds and deploys production.

The project root is the repository root, and the application preset is **Other**. `vercel.json` defines two services in one deployment:

- **frontend** builds the Vite app in `web/`.
- **backend** runs `app.main:app`. The clinic list is included with that function.

`/api/...` is rewritten to the backend. Every other path is rewritten to the frontend.

Storage is a private Vercel Blob store connected to the project. Vercel sets `BLOB_STORE_ID`, and the API uses Vercel’s own credentials for that store. `BLOB_WEBHOOK_PUBLIC_KEY` is created with the store and is unused here.

Set `CLINICALLY_SANE_SALT` on Production and Preview to a long random string and keep it stable. It is the key for the IP hash behind the rate limit and the two-person closure check. Reports still save if it is missing. Each running copy then uses its own salt, so those checks disagree across copies.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. The API serves `web/dist` when that build exists. To work on the interface with a live reload:

```powershell
cd web
npm install
npm run dev
```

The Vite dev server proxies `/api` to `127.0.0.1:8000`.

Local runs write `data/today.json` and `data/stats.json`. Those files, the IP-hash salt, and the SQLite file from the earlier storage design stay out of git.

## Layout

```
app/            FastAPI app, consensus, daily fold, and storage
data/           Clinic list, and local report files when you run it yourself
web/            React map
tests/          Consensus and average checks
vercel.json     Frontend, backend, and routing
```

See [USE_CASE.md](USE_CASE.md) for who this is for and how a city health department could confirm the numbers.

"""Clinically Sane API. Listens on localhost. Notes are checked in-process."""

from __future__ import annotations

import socket
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.consensus import live_estimate
from app.ledger import displayed_averages
from app.moderate import review_note
from app.store import (
    add_closure,
    add_report,
    allow,
    init_db,
    load_clinics,
    load_day,
    reporter_hash,
)

SAST = timezone(timedelta(hours=2))
BBOX = {"south": -34.45, "north": -33.40, "west": 18.28, "east": 19.05}
ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "web" / "dist"
CLINICS = {clinic["id"]: clinic for clinic in load_clinics()}

app = FastAPI(title="Clinically Sane")
init_db()
_nominatim_lock = __import__("asyncio").Lock()
_nominatim_cache: dict[str, dict | None] = {}


class ReportIn(BaseModel):
    clinic_id: str
    minutes: int | None = Field(default=None, ge=0, le=240)
    line_length: int | None = Field(default=None, ge=0, le=300)
    still_waiting: bool
    note: str = ""


class ClosureIn(BaseModel):
    clinic_id: str


def now_sast() -> datetime:
    return datetime.now(SAST)


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=SAST)
    return parsed.astimezone(SAST)


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("cf-connecting-ip") or request.headers.get(
        "x-forwarded-for", ""
    )
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def inside_cape_town(lat: float, lon: float) -> bool:
    return BBOX["south"] <= lat <= BBOX["north"] and BBOX["west"] <= lon <= BBOX["east"]


def snapshot(now: datetime | None = None) -> list[dict]:
    moment = now or now_sast()
    today = moment.date()
    raw_reports, raw_closures, stats = load_day(moment)
    reports_by_clinic: dict[str, list[dict]] = {clinic_id: [] for clinic_id in CLINICS}
    for row in raw_reports:
        if row["clinic_id"] not in reports_by_clinic:
            continue
        reports_by_clinic[row["clinic_id"]].append(
            {
                "id": row["id"],
                "created_at": parse_time(row["created_at"]),
                "minutes": row["minutes"],
                "line_length": row["line_length"],
                "still_waiting": bool(row["still_waiting"]),
                "note": row["note"],
            }
        )
    flags: dict[str, set[str]] = {}
    for row in raw_closures:
        flags.setdefault(row["clinic_id"], set()).add(row["reporter_hash"])

    payload = []
    saved = stats.get("clinics", {})
    for clinic in CLINICS.values():
        rows = reports_by_clinic[clinic["id"]]
        live = live_estimate(rows, moment)
        slot = saved.get(clinic["id"], {})
        today_rows = [row for row in rows if row["created_at"].date() == today]
        seen_rows = [row for row in today_rows if not row["still_waiting"]]
        averages = displayed_averages(slot, seen_rows, today)
        today_flags = len(flags.get(clinic["id"], set()))
        first_candidates = []
        if slot.get("first_day"):
            first_candidates.append(date.fromisoformat(slot["first_day"]))
        if today_rows or today_flags:
            first_candidates.append(today)
        first_day = min(first_candidates) if first_candidates else None
        closure_days = int(slot.get("closure_days") or 0) + (1 if today_flags >= 2 else 0)
        if first_day is None or first_day > today:
            service = {"issue_free_days": 0, "closure_days": 0}
        else:
            span = (today - first_day).days + 1
            service = {"issue_free_days": span - closure_days, "closure_days": closure_days}
        seen_today = [
            row["minutes"]
            for row in today_rows
            if not row["still_waiting"] and row["minutes"] is not None
        ]
        color_minutes = live["minutes"]
        if color_minutes is None and seen_today:
            color_minutes = int(round(sum(seen_today) / len(seen_today)))
        recent = [
            {
                "id": row["id"],
                "time": row["created_at"].strftime("%H:%M"),
                "minutes": row["minutes"],
                "line_length": row["line_length"],
                "still_waiting": row["still_waiting"],
                "note": row["note"],
                "consistent": row["id"] == live["consistent_id"],
                "outlier": row["id"] in live["outlier_ids"],
            }
            for row in today_rows
        ]
        payload.append(
            {
                **clinic,
                "live": {
                    "stale": live["stale"],
                    "active": bool(today_rows),
                    "confidence": live["confidence"],
                    "minutes": live["minutes"],
                    "line_length": live["line_length"],
                    "report_count": live["report_count"],
                    "color_minutes": color_minutes,
                },
                "averages": averages,
                "service": service,
                "closure_today": {
                    "count": today_flags,
                    "confirmed": today_flags >= 2,
                },
                "recent": recent,
            }
        )
    return payload


@app.on_event("startup")
def startup() -> None:
    init_db()
    print("Clinically Sane")
    print("Local: http://127.0.0.1:8000")
    print("Public, from another terminal: cloudflared tunnel --url http://127.0.0.1:8000")
    print("Notes are checked in this app. No model is called.")


@app.get("/api/clinics")
def clinics() -> list[dict]:
    return snapshot()


@app.post("/api/reports")
def create_report(body: ReportIn, request: Request) -> dict:
    if body.clinic_id not in CLINICS:
        raise HTTPException(status_code=404, detail="Unknown clinic")
    if body.minutes is None and body.line_length is None:
        raise HTTPException(status_code=400, detail="Enter minutes or people in line.")
    moment = now_sast()
    ip_hash = reporter_hash(client_ip(request))
    if not allow(ip_hash, body.clinic_id, "report", moment):
        raise HTTPException(status_code=429, detail="Wait 15 minutes before another report here")
    note, note_status = review_note(body.note)
    add_report(
        {
            "clinic_id": body.clinic_id,
            "created_at": moment.isoformat(),
            "minutes": body.minutes,
            "line_length": body.line_length,
            "still_waiting": body.still_waiting,
            "note": note,
            "reporter_hash": ip_hash,
        },
        moment,
    )
    return {"ok": True, "note_kept": note_status == "kept", "note_status": note_status}


@app.post("/api/closures")
def create_closure(body: ClosureIn, request: Request) -> dict:
    if body.clinic_id not in CLINICS:
        raise HTTPException(status_code=404, detail="Unknown clinic")
    moment = now_sast()
    ip_hash = reporter_hash(client_ip(request))
    if not allow(ip_hash, body.clinic_id, "closure", moment):
        raise HTTPException(status_code=429, detail="Wait 15 minutes before another closure flag here")
    added = add_closure(body.clinic_id, moment.date().isoformat(), moment.isoformat(), ip_hash, moment)
    return {"ok": True, "new_flag": added}


@app.get("/api/search")
async def search(q: str) -> dict:
    query = " ".join(q.split())
    if len(query) < 2:
        return {"clinics": [], "place": None}
    needle = query.lower()
    matches = [
        clinic
        for clinic in CLINICS.values()
        if needle in clinic["name"].lower()
        or needle in clinic["suburb"].lower()
        or needle in clinic["address"].lower()
    ][:8]
    if matches:
        return {"clinics": matches, "place": None}
    place = await nominatim(query)
    return {"clinics": [], "place": place}


async def nominatim(query: str) -> dict | None:
    key = query.lower()
    if key in _nominatim_cache:
        return _nominatim_cache[key]
    async with _nominatim_lock:
        if key in _nominatim_cache:
            return _nominatim_cache[key]
        view = f"{BBOX['west']},{BBOX['north']},{BBOX['east']},{BBOX['south']}"
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.get(
                    "https://nominatim.openstreetmap.org/search",
                    params={
                        "q": query,
                        "format": "jsonv2",
                        "limit": 1,
                        "viewbox": view,
                        "bounded": 1,
                    },
                    headers={"User-Agent": "ClinicallySane/1.0 (Cape Town clinic queue map)"},
                )
                response.raise_for_status()
                rows = response.json()
        except httpx.HTTPError:
            _nominatim_cache[key] = None
            return None
        place = None
        if rows:
            lat = float(rows[0]["lat"])
            lon = float(rows[0]["lon"])
            if inside_cape_town(lat, lon):
                place = {"label": rows[0].get("display_name", query), "latitude": lat, "longitude": lon}
        _nominatim_cache[key] = place
        return place


def lan_hint() -> str:
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("8.8.8.8", 80))
        address = probe.getsockname()[0]
        probe.close()
        return address
    except OSError:
        return "127.0.0.1"


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "clinics": len(CLINICS), "lan": lan_hint()}


if DIST.exists():
    assets = DIST / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(DIST / "index.html")
else:

    @app.get("/")
    def index_missing() -> dict:
        return {"detail": "Build the React app with npm run build in web/"}

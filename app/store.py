"""Report storage. The visitor IP is hashed and never written raw.

Local runs use data/today.json and data/stats.json. When a Vercel Blob token
or store is present, those same two documents are the Blob objects.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

from app.ledger import empty_stats, empty_today, fold_day

ROOT = Path(__file__).resolve().parents[1]
SALT_PATH = ROOT / "data" / "salt"
BLOB_ACCESS = "private"
TODAY_NAME = "today.json"
STATS_NAME = "stats.json"

_lock = threading.Lock()
_salt: bytes | None = None
_backend: "_Backend | None" = None


def salt() -> bytes:
    global _salt
    if _salt is not None:
        return _salt
    env = os.environ.get("CLINICALLY_SANE_SALT", "").strip()
    if env:
        _salt = env.encode()
        return _salt
    if SALT_PATH.exists():
        _salt = SALT_PATH.read_text(encoding="utf-8").strip().encode()
        return _salt
    SALT_PATH.parent.mkdir(parents=True, exist_ok=True)
    generated = secrets.token_hex(32)
    SALT_PATH.write_text(generated, encoding="utf-8")
    _salt = generated.encode()
    return _salt


def reporter_hash(ip: str) -> str:
    return hmac.new(salt(), ip.encode(), hashlib.sha256).hexdigest()


def clinics_file() -> Path:
    candidates = [
        ROOT / "data" / "clinics.json",
        Path.cwd() / "data" / "clinics.json",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


def load_clinics() -> list[dict]:
    return json.loads(clinics_file().read_text(encoding="utf-8"))


def _use_blob() -> bool:
    if os.environ.get("BLOB_READ_WRITE_TOKEN") or os.environ.get("VERCEL_BLOB_READ_WRITE_TOKEN"):
        return True
    return bool(os.environ.get("VERCEL") and os.environ.get("BLOB_STORE_ID"))


class _Backend:
    def read(self, name: str) -> dict | None:
        raise NotImplementedError

    def write(self, name: str, document: dict) -> None:
        raise NotImplementedError


class _FileBackend(_Backend):
    def __init__(self) -> None:
        self.root = ROOT / "data"

    def read(self, name: str) -> dict | None:
        path = self.root / name
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def write(self, name: str, document: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / name
        path.write_text(json.dumps(document), encoding="utf-8")


class _BlobBackend(_Backend):
    def read(self, name: str) -> dict | None:
        from vercel.blob import BlobNotFoundError
        from vercel.blob import sync as blob

        try:
            result = blob.get_blob(name, access=BLOB_ACCESS)
        except BlobNotFoundError:
            return None
        return json.loads(result.body.decode("utf-8"))

    def write(self, name: str, document: dict) -> None:
        from vercel.blob import sync as blob

        blob.put_blob(
            name,
            json.dumps(document).encode("utf-8"),
            access=BLOB_ACCESS,
            allow_overwrite=True,
            content_type="application/json",
            cache_control_max_age=0,
        )


def backend() -> _Backend:
    global _backend
    if _backend is None:
        if _use_blob():
            _backend = _BlobBackend()
        elif os.environ.get("VERCEL"):
            raise RuntimeError("Connect a private Vercel Blob store to this project.")
        else:
            _backend = _FileBackend()
    return _backend


def _import_sqlite(today: date) -> tuple[dict, dict] | None:
    db_path = ROOT / "data" / "clinically_sane.db"
    if not db_path.is_file():
        return None
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    reports = [dict(row) for row in connection.execute("SELECT * FROM reports ORDER BY created_at ASC")]
    closures = [dict(row) for row in connection.execute("SELECT * FROM closures ORDER BY created_at ASC")]
    connection.close()
    if not reports and not closures:
        return None
    stats = empty_stats()
    current = empty_today(today.isoformat())
    days = sorted({row["created_at"][:10] for row in reports} | {row["day"] for row in closures})
    for day in days:
        if day >= today.isoformat():
            continue
        stats = fold_day(
            stats,
            {
                "day": day,
                "reports": [_report_from_sqlite(row) for row in reports if row["created_at"][:10] == day],
                "closures": [_closure_from_sqlite(row) for row in closures if row["day"] == day],
            },
            date.fromisoformat(day) + timedelta(days=1),
        )
    current["reports"] = [_report_from_sqlite(row) for row in reports if row["created_at"][:10] == today.isoformat()]
    current["closures"] = [_closure_from_sqlite(row) for row in closures if row["day"] == today.isoformat()]
    if current["reports"]:
        current["reports"][-1]["id"] = max(row["id"] for row in current["reports"])
    return current, stats


def _report_from_sqlite(row: dict) -> dict:
    return {
        "id": row["id"],
        "clinic_id": row["clinic_id"],
        "created_at": row["created_at"],
        "minutes": row["minutes"],
        "line_length": row["line_length"],
        "still_waiting": bool(row["still_waiting"]),
        "note": row["note"],
        "reporter_hash": row["reporter_hash"],
    }


def _closure_from_sqlite(row: dict) -> dict:
    return {
        "clinic_id": row["clinic_id"],
        "day": row["day"],
        "created_at": row["created_at"],
        "reporter_hash": row["reporter_hash"],
    }


def _next_id(reports: list[dict]) -> int:
    if not reports:
        return 1
    return max(int(report["id"]) for report in reports) + 1


def _rollover(now: datetime) -> tuple[dict, dict]:
    store = backend()
    today = now.date().isoformat()
    current = store.read(TODAY_NAME)
    stats = store.read(STATS_NAME)
    if current is None and stats is None and isinstance(store, _FileBackend):
        imported = _import_sqlite(now.date())
        if imported is not None:
            current, stats = imported
            store.write(STATS_NAME, stats)
            store.write(TODAY_NAME, current)
    if stats is None:
        stats = empty_stats()
    if current is None:
        current = empty_today(today)
        store.write(TODAY_NAME, current)
        store.write(STATS_NAME, stats)
        return current, stats
    if current.get("day") == today:
        return current, stats
    if current.get("day"):
        stats = fold_day(stats, current, now.date())
        store.write(STATS_NAME, stats)
    current = empty_today(today)
    store.write(TODAY_NAME, current)
    return current, stats


def init_db() -> None:
    return None


def load_day(now: datetime) -> tuple[list[dict], list[dict], dict]:
    with _lock:
        current, stats = _rollover(now)
        return list(current["reports"]), list(current["closures"]), stats


def allow(ip_hash: str, clinic_id: str, kind: str, now: datetime) -> bool:
    key = f"{ip_hash}|{clinic_id}|{kind}"
    with _lock:
        current, _stats = _rollover(now)
        previous = current["rates"].get(key)
        if previous is not None:
            earlier = datetime.fromisoformat(previous)
            if earlier.tzinfo is None:
                earlier = earlier.replace(tzinfo=now.tzinfo)
            if now - earlier < timedelta(minutes=15):
                return False
        current["rates"][key] = now.isoformat()
        backend().write(TODAY_NAME, current)
        return True


def add_report(row: dict, now: datetime) -> int:
    with _lock:
        current, _stats = _rollover(now)
        report_id = _next_id(current["reports"])
        current["reports"].append(
            {
                "id": report_id,
                "clinic_id": row["clinic_id"],
                "created_at": row["created_at"],
                "minutes": row["minutes"],
                "line_length": row["line_length"],
                "still_waiting": bool(row["still_waiting"]),
                "note": row["note"],
                "reporter_hash": row["reporter_hash"],
            }
        )
        backend().write(TODAY_NAME, current)
        return report_id


def add_closure(clinic_id: str, day: str, created_at: str, ip_hash: str, now: datetime) -> bool:
    with _lock:
        current, _stats = _rollover(now)
        for flag in current["closures"]:
            if flag["clinic_id"] == clinic_id and flag["day"] == day and flag["reporter_hash"] == ip_hash:
                return False
        current["closures"].append(
            {
                "clinic_id": clinic_id,
                "day": day,
                "created_at": created_at,
                "reporter_hash": ip_hash,
            }
        )
        backend().write(TODAY_NAME, current)
        return True

import { useEffect, useMemo, useRef, useState } from "react";
import { MapContainer, Marker, Popup, TileLayer, useMap } from "react-leaflet";
import L from "leaflet";

const CAPE_TOWN = [-33.97, 18.55];
const NEAR_LIMIT_KM = 40;

function distanceKm(lat1, lon1, lat2, lon2) {
  const rad = Math.PI / 180;
  const dLat = (lat2 - lat1) * rad;
  const dLon = (lon2 - lon1) * rad;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(dLon / 2) ** 2;
  return 6371 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(Math.max(0, 1 - a)));
}

function nearestClinic(latitude, longitude, clinics) {
  let clinic = null;
  let distance = Infinity;
  for (const candidate of clinics) {
    const km = distanceKm(latitude, longitude, candidate.latitude, candidate.longitude);
    if (km < distance) {
      clinic = candidate;
      distance = km;
    }
  }
  return { clinic, distance };
}

function pinIcon(color) {
  return L.divIcon({
    className: "",
    html: `<div class="pin" style="background:${color}"></div>`,
    iconSize: [18, 18],
    iconAnchor: [9, 9],
  });
}

function pinColor(clinic) {
  if (clinic.closure_today.count > 0) return "#8e1b1b";
  if (!clinic.live.active) return "#6b7280";
  if (clinic.live.color_minutes != null && clinic.live.color_minutes >= 60) return "#8a4b08";
  return "#005d28";
}

function peopleLabel(count) {
  return `${count} ${count === 1 ? "person" : "people"}`;
}

function pinLabel(clinic) {
  if (clinic.closure_today.count > 0) return "Reported closed today";
  if (!clinic.live.active) return "No reports today";
  if (clinic.live.stale) return "Reports today, no one still waiting";
  const count = clinic.live.report_count;
  const parts = [];
  if (clinic.live.minutes != null) parts.push(`${clinic.live.minutes} min`);
  if (clinic.live.line_length != null) parts.push(peopleLabel(clinic.live.line_length));
  parts.push(`${count} report${count === 1 ? "" : "s"}`);
  return parts.join(", ");
}

function listStatus(clinic) {
  if (clinic.closure_today.count > 0) return "Reported closed today";
  if (!clinic.live.active) return "No reports today";
  if (clinic.live.stale) return "No one still waiting";
  const parts = [];
  if (clinic.live.minutes != null) parts.push(`${clinic.live.minutes} min`);
  if (clinic.live.line_length != null) parts.push(peopleLabel(clinic.live.line_length));
  return parts.join(" · ");
}

function reportLine(report) {
  const parts = [report.time];
  if (report.minutes != null) parts.push(`${report.minutes} min`);
  if (report.line_length != null) parts.push(peopleLabel(report.line_length));
  parts.push(report.still_waiting ? "still waiting" : "already seen");
  return parts.join(" · ");
}

function FlyTo({ target }) {
  const map = useMap();
  useEffect(() => {
    if (!target) return;
    map.flyTo([target.latitude, target.longitude], target.zoom ?? 15, { duration: 0.6 });
  }, [target, map]);
  return null;
}

function FitMap({ layout }) {
  const map = useMap();
  useEffect(() => {
    const timer = setTimeout(() => map.invalidateSize(), 50);
    return () => clearTimeout(timer);
  }, [layout, map]);
  return null;
}

function formatAverage(value, count) {
  if (!count) return "No completed waits yet";
  return `${value} min from ${count}`;
}

function formatLine(value, count) {
  if (!count) return "No line lengths yet";
  return `${value} from ${count}`;
}

export default function App() {
  const [clinics, setClinics] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState([]);
  const [place, setPlace] = useState(null);
  const [fly, setFly] = useState(null);
  const [status, setStatus] = useState("");
  const [searchNote, setSearchNote] = useState("");
  const [nearNote, setNearNote] = useState("");
  const [tab, setTab] = useState("reports");
  const [form, setForm] = useState({
    minutes: "",
    line_length: "",
    still_waiting: true,
    note: "",
  });

  async function load() {
    const response = await fetch("/api/clinics");
    if (!response.ok) return;
    setClinics(await response.json());
  }

  useEffect(() => {
    load();
    const timer = setInterval(load, 10000);
    return () => clearInterval(timer);
  }, []);

  const selected = useMemo(
    () => clinics.find((clinic) => clinic.id === selectedId) ?? null,
    [clinics, selectedId]
  );

  const listed = useMemo(
    () => [...clinics].sort((a, b) => a.name.localeCompare(b.name)),
    [clinics]
  );
  const clinicsRef = useRef(clinics);
  clinicsRef.current = clinics;

  function choose(clinic) {
    setSelectedId(clinic.id);
    setFly({ latitude: clinic.latitude, longitude: clinic.longitude, zoom: 15 });
    setTab("reports");
    setStatus("");
    setSearchNote("");
    setNearNote("");
  }

  function nearMe() {
    if (!navigator.geolocation) {
      setNearNote("This browser has no location.");
      return;
    }
    if (!window.isSecureContext) {
      setNearNote("Location needs a secure page.");
      return;
    }
    setNearNote("Finding your location…");
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const rows = clinicsRef.current;
        if (!rows.length) {
          setNearNote("Clinic list is still loading.");
          return;
        }
        const { clinic, distance } = nearestClinic(
          position.coords.latitude,
          position.coords.longitude,
          rows
        );
        if (!clinic || distance > NEAR_LIMIT_KM) {
          setNearNote("You are outside Cape Town.");
          return;
        }
        choose(clinic);
      },
      (error) => {
        if (error.code === 1) setNearNote("Location permission was denied.");
        else setNearNote("Your location could not be found.");
      },
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 0 }
    );
  }

  async function onSearch(event) {
    event.preventDefault();
    const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
    const data = await response.json();
    setHits(data.clinics);
    setPlace(data.place);
    if (data.clinics.length === 1) choose(data.clinics[0]);
    else if (data.place) {
      setSearchNote("");
      setFly({ latitude: data.place.latitude, longitude: data.place.longitude, zoom: 14 });
    } else if (!data.clinics.length) {
      setSearchNote("Nothing in Cape Town matched that search.");
    } else {
      setSearchNote("");
    }
  }

  function wholeNumber(value) {
    if (value === "") return null;
    const parsed = Number(value);
    return Number.isInteger(parsed) ? parsed : Number.NaN;
  }

  async function submitReport(event) {
    event.preventDefault();
    if (!selected) return;
    const minutes = wholeNumber(form.minutes);
    const lineLength = wholeNumber(form.line_length);
    if (minutes === null && lineLength === null) {
      setStatus("Enter minutes or people in line.");
      return;
    }
    if (Number.isNaN(minutes) || Number.isNaN(lineLength)) {
      setStatus("Use whole numbers.");
      return;
    }
    if (minutes !== null && (minutes < 0 || minutes > 240)) {
      setStatus("Minutes need to be from 0 to 240.");
      return;
    }
    if (lineLength !== null && (lineLength < 0 || lineLength > 300)) {
      setStatus("People in line need to be from 0 to 300.");
      return;
    }
    setStatus("Sending report…");
    const response = await fetch("/api/reports", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        clinic_id: selected.id,
        minutes,
        line_length: lineLength,
        still_waiting: form.still_waiting,
        note: form.note,
      }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      setStatus(typeof data.detail === "string" ? data.detail : "Report not saved.");
      return;
    }
    setStatus(data.note_status === "rejected" ? "Report saved without the note." : "Report saved.");
    setForm({ minutes: "", line_length: "", still_waiting: true, note: "" });
    setTab("reports");
    load();
  }

  async function flagClosed() {
    if (!selected) return;
    setStatus("Sending closure flag…");
    const response = await fetch("/api/closures", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ clinic_id: selected.id }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      setStatus(typeof data.detail === "string" ? data.detail : "Flag not saved.");
      return;
    }
    setStatus(data.new_flag ? "Flagged closed for today." : "You already flagged this clinic today.");
    load();
  }

  return (
    <div className="app">
      <header className="header">
        <h1>Clinically Sane</h1>
        <p>Crowd-sourced Cape Town clinic queues</p>
        <form className="search" onSubmit={onSearch}>
          <input
            aria-label="Suburb, street, or clinic"
            placeholder="Suburb, street, or clinic"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <button type="submit">Search</button>
        </form>
        {hits.length > 1 && (
          <div className="hits">
            {hits.map((clinic) => (
              <button key={clinic.id} type="button" onClick={() => choose(clinic)}>
                {clinic.name}
              </button>
            ))}
          </div>
        )}
        {place && <p>{place.label}</p>}
        {searchNote && <p className="search-note">{searchNote}</p>}
      </header>
      <div className={selected ? "stage has-sheet" : "stage has-list"}>
        {!selected && (
          <aside className="clinic-list">
            <div className="clinic-list-top">
              <button type="button" className="near" onClick={nearMe}>
                Near me
              </button>
              {nearNote && <p className="near-note">{nearNote}</p>}
            </div>
            {listed.map((clinic) => {
              const summary = listStatus(clinic);
              return (
                <button key={clinic.id} type="button" className="clinic-row" onClick={() => choose(clinic)}>
                  <strong>{clinic.name}</strong>
                  <span>{summary ? `${clinic.suburb} · ${summary}` : clinic.suburb}</span>
                </button>
              );
            })}
          </aside>
        )}
        <div className="map-wrap">
          <MapContainer center={CAPE_TOWN} zoom={11} scrollWheelZoom>
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <FlyTo target={fly} />
            <FitMap layout={selected ? "sheet" : "list"} />
            {clinics.map((clinic) => (
              <Marker
                key={clinic.id}
                position={[clinic.latitude, clinic.longitude]}
                icon={pinIcon(pinColor(clinic))}
                eventHandlers={{ click: () => choose(clinic) }}
              >
                <Popup>
                  <strong>{clinic.name}</strong>
                  <br />
                  {pinLabel(clinic)}
                </Popup>
              </Marker>
            ))}
          </MapContainer>
        </div>
        {selected && (
        <aside className="sheet">
            <>
              <div className="sheet-head">
                <div>
                  <h2>{selected.name}</h2>
                  <p className="muted">
                    {selected.kind} · {selected.address}, {selected.suburb}
                  </p>
                </div>
                <button type="button" className="close" onClick={() => setSelectedId(null)}>
                  Close
                </button>
              </div>
              <div className="tabs" role="tablist">
                <button
                  type="button"
                  role="tab"
                  aria-selected={tab === "reports"}
                  className={tab === "reports" ? "tab on" : "tab"}
                  onClick={() => setTab("reports")}
                >
                  Reports
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={tab === "add"}
                  className={tab === "add" ? "tab on" : "tab"}
                  onClick={() => setTab("add")}
                >
                  Add a report
                </button>
              </div>
              {tab === "reports" && (
                <>
              {selected.closure_today.count > 0 && (
                <div className="closed-banner">
                  {selected.closure_today.confirmed
                    ? `Reported closed today by ${selected.closure_today.count} people.`
                    : "1 person reported this clinic closed today."}
                </div>
              )}
              <div className="metrics">
                <div className="metric">
                  <span>Live wait</span>
                  <strong>
                    {selected.live.stale
                      ? "No one still waiting"
                      : selected.live.minutes == null
                        ? "—"
                        : `${selected.live.minutes} min`}
                  </strong>
                </div>
                <div className="metric">
                  <span>People in line</span>
                  <strong>
                    {selected.live.stale || selected.live.line_length == null ? "—" : selected.live.line_length}
                  </strong>
                </div>
                <div className="metric">
                  <span>Agreement</span>
                  <strong>
                    {selected.live.report_count} report{selected.live.report_count === 1 ? "" : "s"} · {selected.live.confidence}
                  </strong>
                </div>
                <div className="metric">
                  <span>Average wait</span>
                  <strong>{formatAverage(selected.averages.all_time, selected.averages.all_time_count)}</strong>
                </div>
                <div className="metric">
                  <span>Average line</span>
                  <strong>{formatLine(selected.averages.line_all_time, selected.averages.line_all_time_count)}</strong>
                </div>
                <div className="metric">
                  <span>Last 7 days</span>
                  <strong>{formatAverage(selected.averages.last_7_days, selected.averages.last_7_days_count)}</strong>
                </div>
                <div className="metric">
                  <span>Service record</span>
                  <strong>
                    {selected.service.issue_free_days} issue-free, {selected.service.closure_days} closed
                  </strong>
                </div>
              </div>
              <h3>Today</h3>
              <p className="hint">Reports expire at midnight. Grey pins have no report today.</p>
              {selected.recent.length === 0 && <p className="muted">No reports yet today.</p>}
              {selected.recent.map((report) => (
                <div key={report.id} className={report.consistent ? "report consistent" : "report"}>
                  <div>
                    <span className="tag">{report.consistent ? "Most consistent · " : report.outlier ? "Outlier · " : ""}</span>
                    {reportLine(report)}
                  </div>
                  {report.note && <div>{report.note}</div>}
                </div>
              ))}
                </>
              )}
              {tab === "add" && (
              <form onSubmit={submitReport}>
                <p className="hint">Enter minutes, people in line, or both.</p>
                <label htmlFor="line">People in your line</label>
                <p className="hint">From the front of your line to you.</p>
                <input
                  id="line"
                  type="number"
                  min="0"
                  max="300"
                  value={form.line_length}
                  onChange={(event) => setForm({ ...form, line_length: event.target.value })}
                />
                <label htmlFor="minutes">Minutes already waited</label>
                <input
                  id="minutes"
                  type="number"
                  min="0"
                  max="240"
                  value={form.minutes}
                  onChange={(event) => setForm({ ...form, minutes: event.target.value })}
                />
                <label>Where you are in the visit</label>
                <div className="choice">
                  <label>
                    <input
                      type="radio"
                      name="state"
                      checked={form.still_waiting}
                      onChange={() => setForm({ ...form, still_waiting: true })}
                    />
                    Still waiting
                  </label>
                  <label>
                    <input
                      type="radio"
                      name="state"
                      checked={!form.still_waiting}
                      onChange={() => setForm({ ...form, still_waiting: false })}
                    />
                    Already seen
                  </label>
                </div>
                <label htmlFor="note">Note, optional</label>
                <textarea
                  id="note"
                  maxLength={200}
                  rows={3}
                  value={form.note}
                  onChange={(event) => setForm({ ...form, note: event.target.value })}
                />
                <div className="actions">
                  <button className="primary" type="submit">Send report</button>
                  <button className="danger" type="button" onClick={flagClosed}>
                    Flag closed today
                  </button>
                </div>
                <p className="hint">Flag this when the clinic has sent people away.</p>
                <p className={/not saved|without the note|Enter |Use whole|need to be/.test(status) ? "status bad" : "status"}>{status}</p>
              </form>
              )}
            </>
        </aside>
        )}
      </div>
    </div>
  );
}

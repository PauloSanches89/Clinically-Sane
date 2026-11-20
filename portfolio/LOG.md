# Portfolio log — Clinically Sane

- Started: 2026-11-17
- Primary shape: data
- Problem: People at Cape Town clinics cannot see a live queue, a saved average wait, or whether a clinic was flagged closed.

## Current bar

- [ ] Real question
- [ ] Ingest
- [ ] Clean
- [ ] Validate
- [x] Query
- [x] Actionable result
- [x] Written break
- [ ] README
- [x] Demo

## Journal

<!-- append below this line -->

### 2026-11-17 — note

- By: agent
- Step: Open the portfolio log before the app files. Primary shape is data because the product is a seeded clinic list plus stored queue reports and the metrics computed from them. The user did not name a shape.
- Why: The build is the clinic dataset and the wait and uptime queries.
- Result: Log created at project start. Earlier research in the chat was not logged.

### 2026-11-17 — data step

- By: agent
- Step: Query the running API after one still-waiting report at Wynberg Clinic, then again after that row was deleted.
- Target: GET /api/clinics
- Why: The live pin has to come from still-waiting reports in the last 90 minutes, and a deleted report must not leave a made-up wait.
- Result: 86 clinics. With one report, live was 40 minutes, 8 people, confidence low, 1 report. The saved average was empty. After the row was removed, Wynberg was stale, 0 reports, minutes null. One closure flag stayed unconfirmed and did not add a closure day.

### 2026-11-17 — prompt change

- By: agent
- Step: Give llama3.2:3b allow and block examples in the note check.
- Target: system, app/moderate.py
- Delta: Added "The wait is too long." is allow, "Only one consulting room is open." is allow, and "I will hurt Nurse Thandi." is block. The note is still treated as data.
- Why: The first prompt blocked both the long-wait complaint and the consulting-room note. The queue numbers were still saved.
- Result: eval not rerun. A direct check then allowed both of those notes, blocked the threat, and blocked a note that named Nurse Thandi. "Staff sent us away at the gate." is still blocked, so that note is dropped.

### 2026-11-17 — break

- By: agent
- Step: Record the note the 3B model still blocks.
- Target: model, llama3.2:3b
- Why: A factual closure note is not a threat, but the model returns block.
- Result: The numbers in that report still publish. The note does not.

### 2026-11-17 — demo

- By: agent
- Step: Open the local app, search Wynberg, and request the public tunnel URL.
- Target: http://127.0.0.1:8000 and the trycloudflare URL
- Why: The same build has to open in a browser and through the tunnel.
- Result: Search opened Wynberg Clinic and the report form. The public URL returned the app HTML. The test report was deleted so the map does not show a fake queue.

### 2026-11-17 — model change

- By: user
- Step: Stop calling llama3.2:3b and reject inappropriate notes with a word and pattern check.
- Target: model, app/moderate.py
- Delta: Removed the Ollama chat call. A note is rejected when it contains a phone number, a 13-digit ID, a threat, a slur, sexual content, or a staff title plus a personal name. A long-wait complaint and "Only one consulting room is open." stay. Queue numbers are still saved.
- Why: The user asked to ignore the model step and reject inappropriate messages another way.
- Result: eval not rerun. Unit checks cover the kept and rejected examples. The sheet says "Report saved. The note was rejected." when the note is dropped.

### 2026-11-17 — data step

- By: user
- Step: Expire queue reports at the end of the South African calendar day instead of after 90 minutes.
- Target: app/consensus.py live estimate, and the clinic list in app/main.py
- Why: A report should stay active for the day it was sent, then leave the pin and the report list.
- Result: A still-waiting report from earlier today stays in the median. A report from the day before is stale. The pin stays grey until that clinic has a report from today.

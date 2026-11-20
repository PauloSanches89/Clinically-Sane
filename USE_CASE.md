# Use case and where this can go

Clinically Sane is a public map of walk-in queues at Cape Town clinics. A person who is already at a clinic, or who has just been seen, can say how long the wait was and how many people were in front of them. Anyone choosing where to go can read that on the map before they travel.

## Why it is useful

Public clinics in Cape Town serve a lot of people who arrive without an appointment. The time that matters is the line in the room, and that line changes through the morning. A clinic that was quiet at 8:00 can be full by 9:30. The official channels that exist today tell you where a clinic is and when it is scheduled to open. They do not tell you the queue you will join if you leave home now.

The people who already know the queue are the people standing in it. A short report from that line is the fastest signal available. The map keeps that signal for the rest of the day, then drops the raw reports at midnight so tomorrow starts clean. The running average stays, weighted by how many finished visits each day actually contained, so a clinic with a long history is not rewritten by two reports on a quiet morning.

That split is the product:

- **Today** answers “what is the line like right now?” from people who are still waiting.
- **The average** answers “what is this clinic usually like?” from people who have already been seen.
- **Closed today** answers “have they sent people away?” and waits for a second independent report before it treats the closure as confirmed.

Someone comparing two nearby clinics can pick the shorter line, leave a full clinic, or stay home when the map says the clinic has turned people away. Clinic staff and health managers can see the same picture without waiting for a monthly report.

The reports are anonymous on purpose. The app hashes the visitor address and never stores the raw IP. Device location is used only in the browser to find the nearest clinic, and it is not uploaded. The useful record is the queue, not the person.

## What the data can and cannot support

A crowd report is a witness statement from the queue. It is timely, and it is also uneven. One person can be wrong about the count. A slow hour can produce no reports at all, which the map shows as a grey pin rather than a claim that the clinic is empty. Notes are checked locally for abuse and can be dropped while the numbers are kept.

The numbers become more trustworthy when more people agree, which is why the live pin uses a median and sets aside a report that disagrees sharply with the others. They become verifiable when an institution that already counts the queue can stand behind the same figure.

## Making the data verifiable with local government

The City of Cape Town and the Western Cape Department of Health already know which facilities are open, who manages them, and, in clinics that use a ticket or folder system, how many people have been registered. Clinically Sane can keep the public map and treat those official feeds as a second source beside the crowd.

Practical integrations, in the order that most improves accuracy:

1. **Official facility list and hours.** Replace the static clinic file with the city’s facility register: name, address, service type, opening hours, and a stable facility id. Reports filed outside published hours can be held back. A clinic that has moved or merged stops appearing under the old pin.

2. **Official closure and diversion notices.** When a facility manager marks the clinic closed, or sends walk-ins to another site, that notice confirms the map immediately. The two-person crowd flag remains as an early warning for the time before the notice is published. The map can show both: “people reported this closed” and “the facility confirmed it.”

3. **A staff counter.** Give each clinic a signed-in counter, or a single shared device at reception, that publishes the number of people waiting from the clinic’s own count. That figure is labeled as the facility count and sits next to the crowd median. Where the clinic uses tickets, the counter can be the ticket system itself: issued tickets minus people already called.

4. **A daily signed summary.** At the end of the day the facility, or the sub-district office, can accept the day’s folded totals: how many crowd reports, the average wait, the average line, and whether a closure was confirmed. Signing that summary does not require patient names. It says the facility recognises the day’s picture, or it replaces the crowd average with the clinic’s own tally.

5. **A pull or push the department already owns.** The app already reduces a day to sums and counts per clinic. A health-department endpoint can receive that fold after midnight, or the department can read it through a partner API. The public Blob store stays private. The department receives aggregates, not IP hashes and not free-text notes, unless it explicitly asks to review notes for abuse.

Verification here means a known institution attaches its name to a number. It does not mean collecting identity documents from people in the queue. Patients keep reporting anonymously. Staff and facility systems add the source that can be audited.

## Where it can go next

- **Sub-district view** for facility managers: which clinics are long this morning, which have a closure flag with no official notice yet, and which have gone quiet.
- **A gap report** once a staff counter exists: crowd median against the facility count, so the department can see where the public picture and the clinic picture diverge.
- **Reporting without the map**, such as a short WhatsApp or USSD flow that files the same report, for people who are in the queue with a basic phone.
- **Opening-hour and stock signals** from the same facility register, so the map can say a clinic is open for immunisation, out of a named medicine, or diverting to a named sister clinic.
- **Other municipalities** once the Cape Town facility id is the pattern. The map, the midnight fold, and the two-source display stay the same. The register and the staff counter change per city.

The first useful step with government is the facility register and the closure notice. Those two feeds make the map’s clinics and its “closed today” state match the city’s own books. The staff counter is the step that makes the wait itself verifiable.

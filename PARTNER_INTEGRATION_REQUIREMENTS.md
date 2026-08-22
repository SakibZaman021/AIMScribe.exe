# AIMScribe — Partner Integration Requirements

**For discussion with CMED, Aalo and Amader Susastho.**
Prepared by AIMS LAB. Draft for the meeting of Sunday, 23 August 2026.

---

## 1. Purpose

AIMScribe records clinical consultations on the doctor's PC, so that a
consultation can later be transcribed and summarised. It cannot know *which*
consultation it is recording. Only the clinical system the doctor is already
using knows that.

This document states exactly what AIMScribe needs from a partner system, what it
does not need, and what it gives back. It is written to be handed to a partner's
engineering team as the basis for a fixed interface.

**One contract, not three.** The same interface is proposed for CMED, Aalo and
Amader Susastho. Negotiating three different integrations would mean three
trigger formats, three sets of identifier rules and three sets of failure modes
to support across the fleet. Every requirement below is deliberately written to
be implementable by any of the three without reference to the others.

---

## 2. Scope

**In scope:** the signals a partner system sends to the AIMScribe agent running
on the same PC, the identifiers those signals carry, and the security conditions
under which the agent accepts them.

**Out of scope for the partner:** audio capture, storage, encryption,
transcription, archival and deletion. All of these are AIMS LAB's
responsibility and require nothing from the partner.

---

## 3. What the partner does **not** have to do

Stated first, because it is the shortest section and it removes most of the
usual objections.

| Not required | Why |
|---|---|
| Hold or manage any cryptographic key | Authorisation is signed by the AIMS LAB backend, not by the partner |
| Store, receive or transmit audio | Audio never leaves the doctor's PC except to the AIMS LAB archive |
| Change any database schema | Every field requested below already exists in the partner's system |
| Write to any AIMS LAB system | The partner sends signals; it is never asked to persist our data |
| Host, package or update AIMScribe | AIMS LAB installs and maintains the agent on each PC |
| Provide patient names, clinical notes or history | AIMScribe needs an identifier only, never content |
| Provide a server-to-server integration | The signals originate in the doctor's browser session |

The total change on the partner side is: **emit two signals from pages the
doctor already uses, and confirm a small number of facts about identifiers.**

---

## 4. Functional requirements

Priorities: **M** mandatory — integration cannot work without it. **S** should
have — significant loss of function or safety without it. **C** could have.

### R1 (M) — Consultation start signal

When a doctor opens a patient's details or history, the partner system must
signal the AIMScribe agent, carrying five fields.

| Field | Meaning | Constraint |
|---|---|---|
| `patient_id` | The patient being consulted | See R3 |
| `doctor_id` | The doctor conducting the consultation | See R3 |
| `clinic_id` | The clinic or facility | See R3 |
| `start_time` | When the consultation began | ISO 8601 with timezone offset |
| `date` | Consultation date | ISO 8601 date |

**Rationale.** AIMScribe deliberately has no way to start a recording by itself
and no way for a doctor to type in who they are seeing. An earlier version
allowed free text and consultations were filed under clinics and doctors that
did not exist. The doctor is taken from this signal on every consultation and
never inferred from the machine, because a consulting room runs two shifts and
the same laptop serves different doctors through the day.

**A signal that does not name a doctor is refused, not guessed.** This is
intentional and is not a defect.

### R2 (M) — Consultation complete signal

When the doctor performs the action that marks the consultation clinically
finished — for CMED, pressing **build prescription** to convert the tabular
entry into a prescription — the partner system must send a second signal.

It carries no clinical content. A single indication that the consultation is
complete is sufficient.

**Rationale.** This is the safety interlock that prevents one patient's
consultation being filed under another's identity. Without it, a doctor who
opens the wrong patient's record mid-consultation would immediately end the
current recording and start a new one under the wrong patient. With it, a start
signal arriving before the completion signal is ignored, and the recording in
progress is protected.

Recording does **not** stop when this signal arrives. Doctors typically counsel
the patient for a further one to two minutes, and that is clinical content worth
keeping.

**Question for each partner:** what is the equivalent action in your system, and
does it occur for every patient? If a meaningful share of consultations end
without it, an alternative completion signal is needed.

### R3 (M) — Identifier stability and format

All three identifiers must satisfy:

- **Character set and length:** `A–Z a–z 0–9 _ -`, between 1 and 64 characters.
  Enforced by the agent; a value outside this set is refused.
- **Stable:** an identifier must refer to the same doctor, patient or clinic
  permanently. Reassigning an identifier corrupts historical records.
- **Opaque:** identifiers must not be, or contain, patient names, national ID
  numbers or phone numbers.

**Rationale.** `clinic_id` and `patient_id` become directory and file names in
the archive. This is why the character set is restrictive, and why an identifier
that is later reused cannot be corrected after the fact.

**Question for each partner:** confirm your identifiers meet this. If any
contain other characters, a deterministic transformation must be agreed **now**,
in writing, and never changed.

### R4 (M) — Declared web origin

The partner must supply the exact origin of every deployment that will send
signals — production, staging and any regional variant. For example
`https://cmed.example.com`.

**Rationale.** The agent accepts signals only from an exact allow-list of
origins. This is the primary defence preventing any other website the doctor
visits from starting a recording. Wildcards are rejected by the agent at
startup. A missing origin is refused.

**Consequence the partner should plan for:** changing the site's domain, or
adding a new one, requires a configuration change on every laptop. Give AIMS LAB
advance notice of any planned change.

### R5 (M) — Patient consent

AIMScribe refuses to record without a positive record that the patient consented.
This is enforced in three independent places and is not a formality.

**Question for each partner:** does your system capture consultation-recording
consent today?

- **If yes:** send the consent state and the method (verbal, written) with R1.
- **If no:** AIMS LAB will capture it in the AIMScribe interface before recording
  begins. This requires no partner change, but the partner should be aware the
  doctor will see an additional prompt.

This must be settled before deployment. It is a clinical governance question,
not a technical one.

### R6 (S) — Doctor and clinic register

AIMS LAB needs a current list of doctors and clinics: identifier, display name,
clinic membership, and active status.

A periodic export is sufficient. A read-only API endpoint is preferable.

**Rationale.** The AIMS LAB backend validates that a doctor named in a signal
genuinely practises at that clinic before authorising a recording. Without a
register this check cannot be made, and a mistyped or stale identifier would
file a consultation under a doctor who does not exist there.

### R7 (S) — Notification of register changes

Notice when a doctor joins, leaves or moves between clinics, and when a clinic is
added, renamed or closed.

**Rationale.** A clinic's identifier is permanent because it names the archive
folder. Display names can change freely. AIMS LAB needs to know which has
happened.

### R8 (C) — Doctor display name

The doctor's name for display in the AIMScribe interface. Not required for
correctness; the identifier is authoritative.

---

## 5. What AIMScribe gives back

Available to any partner that wants it. None of it is mandatory to receive.

| Signal | Content |
|---|---|
| Recording state | Started, paused with reason, resumed, stopped with reason |
| Session reference | An opaque identifier for the recording, for cross-reference |
| Failure notice | Recording could not start or could not continue, and why |

**Not provided to the partner:** audio, transcripts or summaries. Those follow a
separate clinical governance route, not this interface.

---

## 6. Interface

### 6.1 Delivery

The AIMScribe agent listens on the doctor's own PC at **`127.0.0.1:5050`**. It
is not reachable from the network and holds no public address.

Signals are sent from the doctor's browser session on that PC. The partner's
server never contacts the agent and does not need to.

### 6.2 Failure handling — required behaviour

| Condition | Required partner behaviour |
|---|---|
| Agent not running or not reachable | **Continue normally.** Do not block, warn repeatedly, or interrupt the doctor |
| Agent refuses the signal | Log it. Do not retry in a loop |
| Any error at all | The consultation must proceed |

**Rationale, and the most important line in this document: recording is
secondary to care.** A failure in AIMScribe must never prevent a doctor from
seeing a patient. AIMS LAB monitors agent health independently and does not rely
on the partner to report it.

### 6.3 Ordering and duplicates

- Repeated completion signals for the same consultation are harmless; the agent
  treats them as idempotent. Doctors revise prescriptions, and each revision may
  legitimately re-send.
- A start signal for a patient already being recorded is ignored, not an error.
- Signals must arrive in the order the doctor performed the actions.

---

## 7. Security

| Requirement | Owner |
|---|---|
| Exact-origin allow-list; no wildcards | AIMS LAB enforces; partner supplies origins (R4) |
| Doctor identity from an authenticated partner session | Partner |
| Recording authorisation signed and validated | AIMS LAB |
| Clinic in the signal must match the clinic the PC is registered to | AIMS LAB enforces; mismatch refuses to record |
| Audio encrypted on the PC and in transit | AIMS LAB |
| Agent registered to a specific clinic before it can record at all | AIMS LAB |

Two properties worth stating plainly to the partner:

**A PC that is not registered by AIMS LAB cannot contribute a recording.**
Installing the software is not sufficient. Nothing it captures can be filed.

**The partner's system is not a route to patient audio.** Audio is encrypted on
the PC under a key held only by that machine and travels only to the AIMS LAB
archive. A fault or compromise in the partner's system cannot expose recordings.

---

## 8. Technical risks to resolve

Raise these at the meeting; they affect implementation cost on the partner side.

**R8.1 — Browser restrictions on local requests.** Current Chrome versions
restrict requests from a public website to a local address, and may require
additional permission handling. This must be **verified on the exact browser
versions deployed in the clinics** before either side commits to a design. It is
the single most likely cause of an integration that works in development and
fails in the clinic.

**R8.2 — HTTPS site contacting a local address.** Browsers generally treat
`127.0.0.1` as trustworthy, so this normally works, but it must be confirmed
against the deployed browsers rather than assumed.

**R8.3 — Corporate browser policy.** Managed browsers, extensions or endpoint
security may block local requests. Needs confirmation from whoever administers
the clinic PCs.

**R8.4 — Clock accuracy.** Recording authorisation is valid for 60 seconds.
A PC whose clock is more than about a minute out will fail to start recordings,
and the error will not obviously point at the clock. Clinic PCs must have time
synchronisation enabled. *This has already been observed in the field and is the
leading explanation for at least one reported authorisation failure.*

**R8.5 — Antivirus and endpoint protection.** May interfere with local
communication or with the agent's disk writes. Needs an allow-list entry on
managed machines.

---

## 9. Per-partner status

To be completed during the meeting.

| Item | CMED | Aalo | Amader Susastho |
|---|---|---|---|
| Start signal (R1) exists today | | | |
| Completion signal (R2) — equivalent action | build prescription | | |
| Share of consultations with no completion action | | | |
| Identifiers meet R3 format | | | |
| Production origin(s) (R4) | | | |
| Consent captured today (R5) | | | |
| Register available (R6) | | | |
| Clinic identifier mapping agreed | | | |
| Technical contact | | | |
| Target integration date | | | |

---

## 10. Responsibilities

| Area | AIMS LAB | Partner |
|---|---|---|
| Two signals from the clinical system | — | Build |
| Identifier definitions and stability | Consume | Define and guarantee |
| Origin declaration and change notice | Configure | Supply |
| Agent installation and registration on each PC | Own | — |
| Audio capture, encryption, archive, deletion | Own | — |
| Transcription and summarisation | Own | — |
| Consent capture | Own **if** partner does not | Own **if** already captured |
| Doctor and clinic register | Consume | Supply |
| Agent monitoring and support | Own | — |
| Clinic PC time sync, antivirus policy | Advise | Arrange |

---

## 11. Acceptance criteria

Integration is complete for a partner when all of the following pass at one
pilot site:

1. Opening a patient's details starts a recording attributed to the correct
   doctor, patient and clinic.
2. A recording never starts without a completion signal having ended the
   previous one.
3. Opening a different patient mid-consultation does **not** interrupt the
   recording in progress.
4. After a completion signal, opening the next patient ends the previous
   recording and begins the next with no loss of audio between them.
5. A consultation that ends without a completion signal can still be closed
   cleanly by the doctor.
6. With the agent stopped, the partner system behaves entirely normally.
7. A signal from any origin other than the declared one is refused.
8. A signal naming a clinic other than the PC's registered clinic is refused.
9. Twenty consecutive consultations complete with correct attribution and no
   manual intervention.

---

## 12. Questions to settle on Sunday

**For every partner:**

1. What action marks a consultation clinically complete, and does it happen for
   every patient? (R2 — the interlock depends on it)
2. Do your identifiers meet the format in R3, and are they permanent?
3. What are your exact production and staging origins?
4. Is recording consent captured today? If not, do you accept that AIMScribe
   prompts for it?
5. Can you provide a doctor and clinic register, and notify us of changes?
6. Who is the technical contact, and what is a realistic implementation date?

**For CMED specifically:**

7. Confirm the five fields in R1 match what is sent when patient details or
   history is opened.
8. Confirm the build-prescription action can emit R2.
9. Confirm how CMED clinic identifiers map to the archive clinic identifiers
   already in use.

**For Aalo and Amader Susastho:**

10. Does an equivalent to the patient-details trigger exist, or must it be
    built?
11. Are these separate systems, or deployments of a shared platform? A shared
    platform means one implementation serves both.

---

## 13. Glossary

| Term | Meaning |
|---|---|
| Agent | The AIMScribe software on the doctor's PC |
| Registration | The one-time process binding a PC to a clinic. Without it the PC cannot contribute recordings |
| Signal | A message from the partner system to the agent |
| Session | One recorded consultation |
| Archive | AIMS LAB's long-term encrypted store |
| Segment | A short clip of a consultation, sealed and verified independently |

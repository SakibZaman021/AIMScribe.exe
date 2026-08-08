# AIMScribe

Clinical consultation recording for AIMS LAB. A Windows tray agent captures
doctor–patient audio in the consulting room, and every recording reaches the
hospital's archive with cryptographic evidence that it arrived complete and
unaltered.

Agent version **2.3.1**, wire protocol **2**.

Two things live in this repository:

| Directory | What it is |
|---|---|
| `recorder/` | The tray agent installed on each consulting-room PC |
| `cmed-web/` | The CMED web application that starts and stops recordings |

The AI backend, the database and the archive worker live in
[AIMScribe_Backend_Render](https://github.com/SakibZaman021/AIMScribe_Backend_Render).

> `aimslab-server/` is **v1 leftover code and is not part of the running
> system.** It exposes an unauthenticated upload endpoint and posts to
> `/api/v1/session/create`. The real AIMS LAB server component is
> `archive_worker/` in the backend repository, which is outbound-only. Do not
> deploy `aimslab-server/`.

---

## Where to go next

| Document | Answers |
|---|---|
| **This file** | What the system is and how a consultation travels through it |
| [`OPERATIONS.md`](OPERATIONS.md) | How do I enrol a laptop, add a clinic, or fix a failure? |
| [`TARGET_ARCHITECTURE.md`](TARGET_ARCHITECTURE.md) | How is it built, and why that way? Data model and capacity |
| [`INTEGRATION_SPECIFICATION.md`](INTEGRATION_SPECIFICATION.md) | Exact contract: grants, WebSocket commands, HTTP routes |
| [`SECURITY_HARDENING_PLAN.md`](SECURITY_HARDENING_PLAN.md) | The v1 defects this system was built to fix (historical record) |
| [`ARCHITECTURE_DESIGN.md`](ARCHITECTURE_DESIGN.md) | Superseded first-generation design notes, kept for history |

---

## The three identities

Almost every design decision follows from keeping these separate. Getting this
wrong is what produced misfiled consultations in v1.

| Identity | Where it comes from | Can the browser change it? |
|---|---|---|
| **Hospital** | The machine's enrolment. Fixed when an administrator enrols the PC. | No |
| **Doctor** | The CMED grant, per consultation. | Only from CMED's register |
| **Patient** | The CMED grant, per consultation. | Only from CMED |

A consulting room runs two shifts. The morning and afternoon doctors share the
same laptop, so the doctor **cannot** be a property of the machine — that filed
afternoon consultations under the morning doctor, silently, in the filename.
The hospital, by contrast, never changes for a given PC, so it comes from
enrolment and the browser is never asked.

`hospital_id` is also the top-level archive folder name. A hospital's display
name can be changed at any time; **its `hospital_id` must never change**, or
existing archive paths and enrolled devices stop lining up.

---

## How a consultation travels

```
CONSULTING-ROOM PC              OBJECT STORAGE            AIMS LAB SERVER
                                (Cloudflare R2,              (archive)
                                    transit)

CMED page: Start
     │  grant: EdDSA JWT, 60 s, single use, signed by CMED
     ▼
  agent verifies signature, issuer, audience, expiry and consent
     │
  ULID session id minted locally  ← recording starts even with the backend down
     │
  microphone 44.1 kHz mono 16-bit WAV
     │
  clip closes on a quiet patch between 30 s and 60 s
     ├──► encrypted spool on disk (AES-256-GCM, DPAPI-wrapped key)
     │
     └──► presigned PUT ──────────► clip stored
                                        │
                        backend re-reads the object and re-hashes it;
                        a mismatch quarantines the session
                                        │
  doctor: Stop                          │
     │  signed close entry              │
     ▼  chain verified server-side      │
                                   archive worker pulls ──► clips joined into one WAV
                                   (outbound only,               │
                                    no inbound ports)   re-read from disk and hashed
                                                                 │
                                          D:\AIMSLAB_AUDIO_STORAGE\
                                            HOSP001\DR001\2026-08-04\
                                              1034GS6_DR001_HOSP001_15_01_15_12_2026_08_04\
                                                └─ ….wav + manifest.json
                                                                 │
                                                    purge receipts signed (Ed25519)
                                                                 │
     ◄───────────────────────────────────────────────────────────┘
  agent verifies each receipt, waits out the 24 h grace, deletes its local copy
                                        │
                              clips deleted from R2
```

**Local audio is never deleted because an upload returned HTTP 200.** It is
deleted only against a server-signed receipt proving the archive copy exists and
hashes correctly. If the archive is lost, no receipt is issued and nothing is
deleted.

---

## Integrity

Every session carries an Ed25519 hash chain signed by a machine-bound device
key. The chain covers the open, every segment, every pause and resume, and the
close. Each entry commits to the hash of the one before it.

Deleting, reordering or substituting audio breaks the chain, and a broken chain
quarantines the session instead of archiving it. The chain is verified on the
server at close, not on the machine that produced it.

A gap in a recording is explained rather than unaccounted for: pausing requires
a reason, a pause past five minutes requires a named supervisor, and both are
written into the chain.

Three further checks are worth knowing:

- **`/segment/commit` re-reads the uploaded object from storage and recomputes
  its SHA-256.** A client's claim about what it uploaded is never trusted.
- **The archive worker re-reads the joined WAV from disk and hashes it** before
  reporting the session archived, which proves the bytes actually landed rather
  than sitting in a write cache.
- **`audit_log` is append-only, enforced by a database trigger** that raises on
  both `UPDATE` and `DELETE`. The record that a session existed outlives the
  session rows themselves.

---

## Running it

### Consulting-room PC

Run `AIMScribeSetup.exe` as administrator. The installer asks for the backend
URL, the allowed CMED origin, and a one-time enrolment token; it then writes
`.env`, installs the pinned public keys, registers a logon task, and stages the
token for first start.

**No batch scripts are ever placed on a clinical machine, and the tray app
cannot be exited by a non-administrator.** See [`OPERATIONS.md`](OPERATIONS.md)
for the enrolment procedure.

For development from source:

```powershell
cd recorder
pip install -r requirements.txt
python scripts\dev_keys.py     # once: generates grant and receipt key pairs
python main.py
```

### CMED web

```powershell
cd cmed-web
npm install
npm run dev
```

Copy `.env.local.example` to `.env.local` first and fill it in. The grant
signing key (`AIMS_GRANT_PRIVATE_KEY`) lives only in this server's environment —
it never reaches the browser, and the agent holds only the public half.

Check any deployment with `GET /api/config-check`, which reports which variables
are set without ever returning a value.

### Backend and archive

See the backend repository. The archive worker runs on the AIMS LAB server and
makes only outbound connections, so that machine needs no open ports and holds
no bucket credentials.

---

## Configuration

`recorder/.env.example` documents every setting. The ones that matter most:

| Setting | Default | Why it matters |
|---|---|---|
| `AIMS_ALLOWED_ORIGINS` | *(none)* | Exact origins only, no wildcards. The agent refuses the WebSocket handshake from anything else, which is what stops a random web page starting a recording. |
| `AIMS_REQUIRE_GRANT` | `true` | Never disable. Recording requires a CMED-signed, single-use grant. |
| `AIMS_SEGMENT_MIN_SECONDS` / `MAX` | `30` / `60` | A clip is the unit of upload, retry and loss. At three minutes a failure risked three minutes; at one, it risks one. |
| `AIMS_PURGE_GRACE_HOURS` | `24` | How long receipted audio is kept locally as a safety net. |
| `AIMS_SPOOL_MAX_BYTES` | 40 GB | About three weeks of backend downtime at 44.1 kHz. |
| `AIMS_ALLOW_PLAINTEXT_KEYSTORE` | `false` | Development only. Must be false on a clinical PC. |

Audio is **44.1 kHz, mono, 16-bit WAV PCM: about 318 MB per hour.** Changing any
of those three values changes the archive contract.

The agent refuses to accept sessions when `Config.validate()` reports a problem
(missing origins, missing pinned keys, placeholder API key) and reports the
reason in the tray, rather than running in a quietly insecure state.

### Machine state

State lives outside the install directory so `%ProgramFiles%` can stay read-only
to the logged-in user:

```
%PROGRAMDATA%\AIMScribe\spool    encrypted segment spool
%PROGRAMDATA%\AIMScribe\keys     DPAPI-wrapped device key, pinned public keys
%PROGRAMDATA%\AIMScribe\state    device.json, device.token, enrollment.token
%PROGRAMDATA%\AIMScribe\logs     rotated logs, identifiers redacted
```

---

## Tests

```powershell
cd recorder
python -m pytest
```

Covers the hash chain, the spool, the segmenter, and a regression for each
security defect listed in `SECURITY_HARDENING_PLAN.md`.

---

© 2026 AIMS LAB. Proprietary.

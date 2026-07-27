# AIMScribe

Clinical consultation recording for AIMS LAB. A Windows tray agent captures
doctor–patient audio, and every recording reaches the hospital's archive with
evidence that it arrived complete and unaltered.

Two things live in this repository: the agent that runs on each doctor's PC
(`recorder/`) and the CMED web application that starts and stops recordings
(`cmed-web/`). The AI backend and the archive worker live in
[AIMScribe_Backend_Render](https://github.com/SakibZaman021/AIMScribe_Backend_Render).

---

## How a consultation travels

```
DOCTOR'S PC                    OBJECT STORAGE            AIMS LAB SERVER
                                  (transit)                 (archive)

CMED page: Start
     │  grant, 60s, single use, signed by CMED
     ▼
  agent verifies it
     │
  ULID minted locally  ← recording starts even with the backend down
     │
  microphone 44.1 kHz WAV
     │
  clip closes every ~180s
     ├──► encrypted spool on disk (AES-256-GCM, DPAPI-wrapped key)
     │
     └──► presigned PUT ──► clip stored
                              │
              backend re-reads the object and re-hashes it;
              a mismatch quarantines the session
                              │
  doctor: Stop                 │
     │  signed close entry     │
     ▼                         │
                          archive worker pulls ──► clips joined into one WAV
                          (outbound only, no                │
                           inbound ports)      re-read from disk and hashed
                                                            │
                                               HOSPITAL/DOCTOR/DATE/
                                               45_DR001_HOSP001_1432-1522_20260727.wav
                                                            │
                                               purge receipts signed (Ed25519)
                                                            │
     ◄──────────────────────────────────────────────────────┘
  agent verifies each receipt, then deletes its local copy
                              │
                    clips deleted from object storage
```

Local audio is never deleted because an upload returned HTTP 200. It is deleted
only against a server-signed receipt proving the archive copy exists and hashes
correctly. If the archive is lost, no receipt is issued and nothing is deleted.

---

## Integrity

Every session carries an Ed25519 hash chain, signed by a machine-bound device
key, covering the open, each segment, each pause and resume, and the close.
Deleting, reordering or substituting audio breaks the chain, and a broken chain
quarantines the session rather than archiving it.

A gap in a recording is explained rather than unaccounted for: pausing requires
a reason, long pauses require a supervisor, and both are written into the chain.

---

## Running it

### Doctor PC

Install the signed build with `recorder/install.ps1` as administrator. It
registers a logon task, writes configuration, and enrols the device with a
one-time token from an administrator. No batch scripts are placed on a clinical
machine and the tray app cannot be exited by a non-administrator.

For development:

```powershell
cd recorder
pip install -r requirements.txt
python scripts\dev_keys.py     # once: grant and receipt key pairs
python main.py
```

### CMED web

```powershell
cd cmed-web
npm install
npm run dev
```

Copy `.env.local.example` to `.env.local` first and fill it in.

There is no doctor login. Doctors are chosen from a register:

```
AIMS_DOCTORS=DR001:Dr Sakib Zaman,DR002:Dr Ayesha Rahman
```

That keeps the value a real person rather than free text — without it,
`doctor_id` is whatever the browser sends, and the archive is filed by doctor,
so a typo creates a folder nobody will ever open again.

It is a selection, not proof of who is at the keyboard. Anyone who can open the
page can pick any name on the list. The hospital cannot be faked the same way:
the agent checks the grant against the hospital its device was enrolled at and
refuses a mismatch. When attribution has to hold up in a dispute, replace
`resolveDoctor()` in `src/lib/doctors.ts` with the hospital's identity provider;
nothing else changes.

Check a deployment with `GET /api/config-check`, which reports which variables
are set without ever returning a value.

### Backend and archive

See the backend repository. The archive worker runs on the AIMS LAB server and
makes only outbound connections, so that machine needs no open ports.

---

## Configuration

`recorder/.env.example` documents every setting. The ones that matter most:

| Setting | Why it matters |
|---|---|
| `AIMS_ALLOWED_ORIGINS` | Exact origins only. The agent refuses the WebSocket handshake from anything else, which is what stops a random web page starting a recording. |
| `AIMS_REQUIRE_GRANT` | Never disable. Recording requires a CMED-signed, single-use grant. |
| `AIMS_PURGE_GRACE_HOURS` | How long receipted audio is kept locally as a safety net. 24 in production. |
| `AIMS_SPOOL_MAX_BYTES` | 40 GB is about three weeks of backend downtime at 44.1 kHz. |
| `AIMS_ALLOW_PLAINTEXT_KEYSTORE` | Development only. Must be false on a clinical PC. |

Audio is 44.1 kHz, mono, 16-bit WAV PCM: about 318 MB per hour. Changing those
values changes the archive contract.

---

## Tests

```powershell
cd recorder
python -m pytest
```

67 tests, including a regression for each security defect listed in
`SECURITY_HARDENING_PLAN.md`.

---

## Documents

- `TARGET_ARCHITECTURE.md` — the design, the data model, and capacity planning
- `SECURITY_HARDENING_PLAN.md` — the v1 defects this system was built to fix
- `INTEGRATION_SPECIFICATION.md` — the CMED integration contract
- `ARCHITECTURE_DESIGN.md` — earlier design notes, kept for history

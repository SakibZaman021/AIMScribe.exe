# AIMScribe — Target Architecture (self-hosted on the AIMS LAB server)

**Date**: 2026-07-26 · Supersedes `ARCHITECTURE_DESIGN.md` where they conflict.
Companion document: `SECURITY_HARDENING_PLAN.md` (defect list and controls).

---

## 1. Requirements as stated

| # | Requirement | Design section |
|---|---|---|
| R1 | `AIMScribe.exe` runs in the system tray on every doctor PC; the backend is hosted on the AIMS LAB server | §2, §8 |
| R2 | Records the doctor–patient conversation so that **nobody can tamper with the audio data collection** | §4 |
| R3 | Clips go through **as they are produced** (streamed, not batched at the end) | §5 |
| R4 | Once saved, the full audio is **auto-deleted from the doctor's PC** and lives only on the AIMS LAB server | §6 |
| R5 | AIMS LAB storage sorted **hospital → doctor → date → patient audio files** | §7 |
| R6 | Metadata in a database, so the exact file location on the AIMS LAB server is discoverable from the DB | §7.3 |

---

## 2. Target topology

```
DOCTOR PC (×~20, across 7–10 hospitals)          AIMS LAB SERVER (single site, self-hosted)
──────────────────────────────────────           ────────────────────────────────────────────
AIMScribe agent (tray, user session)             ┌ nginx / Caddy — TLS + mTLS termination
  · PyAudio capture                              │
  · Opus encode 16 kHz                           ├ aimscribe-api (FastAPI)
  · segment 170–190 s                            │    /device/enroll        (mTLS)
  · encrypted spool on disk  ◀── survives        │    /session/open
  · hash-chained manifest         outage         │    /segment/authorize    → presigned PUT
  · presigned PUT ──────────────────────────────▶│    /segment/commit       (sha256 verified)
  · delete only on signed receipt ◀──────────────│    /session/close
  · heartbeat every 30 s ───────────────────────▶│    /purge-receipt        (signed)
                                                 │    /heartbeat
AIMScribe watchdog service                       │
  · restarts the agent, reports tampering        ├ MinIO  (landing zone, hot, 72 h)
                                                 │
cmed-web (browser, doctor's PC)                  ├ ingest-worker  (bucket notification → archive)
  · ws://localhost:5050/ws                       │    verifies sha256, writes the sorted tree,
  · signed grant from CMED server                │    records metadata, then authorises purge
                                                 │
                                                 ├ PostgreSQL  (metadata + hash-chained audit)
                                                 ├ Redis  (queue)
                                                 └ D:\AIMSLAB_AUDIO_STORAGE\  (archive tree, §7)
```

Three deliberate choices, each of which removes a class of failure:

1. **MinIO is the landing zone, not an afterthought.** The agent uploads via presigned PUT, so the AIMS LAB
   server needs **no inbound file-upload endpoint** at all. Delete `POST /receive-recording` and
   `POST /receive-clip` (`aimslab-server/main.py:87-165`) — they are the arbitrary-file-write and
   unauthenticated-PHI-upload holes from the hardening plan, and this design does not need them.
2. **The archive tree is written by a server-side worker**, never by a client. Clients cannot choose where
   bytes land, so a compromised agent cannot write outside its own session.
3. **The agent's local spool is the outage buffer.** Self-hosting means the AIMS LAB server is a single
   point of failure for all 7–10 hospitals; the spool converts an outage from data loss into delay.

---

## 3. What changes from today's code

| Today | Target | Why |
|---|---|---|
| Recorder POSTs the full WAV to `:7000` (`file_forwarder.py`) | Presigned PUT to MinIO; server-side ingest | Kills the inbound upload surface |
| Audio held entirely in RAM (`recorder.py:61`) | Encrypted incremental spool, fsync'd | Crash = total loss today |
| WAV 32 kHz/16-bit | Opus 24 kbps @ 16 kHz | 21× smaller; Whisper resamples to 16 kHz anyway (§9) |
| Delete after HTTP 200 (`clip_uploader.py:256`, `file_forwarder.py:115`) | Delete only on a **signed purge receipt** | Today a lost server-side write silently destroys the only copy |
| `recordings/{patient_id}/` | `HOSPITAL/DOCTOR/DATE/` (§7) | R5 |
| No DB (folder listing is the index) | Postgres is the index (§7.3) | R6 |
| No integrity chain | Per-segment hash chain, device-signed | R2 |
| Doctor can exit from the tray menu (`main.py:123-127`) | Watchdog service; exit is an audited, authorised action | R2 |

---

## 4. R2 — making the collection tamper-*evident*

One correction up front, because the rest of the design depends on it: **you cannot make local audio
capture tamper-proof.** Anyone with physical access can unplug the microphone, and anyone with local
Administrator rights can kill any process. Vendors who claim otherwise are wrong.

What is achievable, and is the actual industry standard for evidentiary recording, is that **every
interruption is detected, attributed, and impossible to conceal.** Design for that:

### 4.1 Continuity — an unforgeable chain

Each segment gets a chain entry, computed on the agent and signed with the device's TPM-held key:

```
seq_no   = 1, 2, 3, … (no gaps permitted)
h(n)     = SHA256( seq_no ‖ session_id ‖ sha256(audio_bytes) ‖ captured_start ‖ captured_end ‖ h(n-1) )
h(0)     = SHA256( session_id ‖ device_id ‖ doctor_id ‖ patient_ref ‖ opened_at )
signature = Ed25519_sign( device_key, h(n) )
```

The server stores `h(n)` per segment and recomputes the chain at `/session/close`. This makes the
following impossible to hide, rather than merely difficult:

- deleting a segment → chain break at the next entry
- reordering segments → recomputation fails
- substituting audio → `sha256(audio_bytes)` mismatch
- re-recording the whole session → `h(0)` cannot be reproduced without the TPM key
- editing the local spool → per-segment hash was already committed to the server

Because the private key is non-exportable in the TPM, the doctor's PC can sign but a copy of its disk
cannot. Store the chain head in the audit log too, so the DB itself cannot be quietly rewritten.

### 4.2 Interruption detection

Emit an audit event, and an integrity alert, for each of:

| Condition | How the agent detects it |
|---|---|
| Process killed / PC powered off mid-session | Watchdog service sees the agent gone; server sees the heartbeat stop |
| Agent stopped and restarted | Orphaned spool found at startup with an unclosed session |
| Microphone muted or gain zeroed | WASAPI endpoint volume/mute polling |
| Microphone unplugged or switched | `IMMNotificationClient` device-change callback |
| Physically blocked mic | Rolling RMS telemetry per segment; a whole session near the noise floor is anomalous |
| Clock tampering | Segment timestamps vs. `time.monotonic()` vs. server time on every commit |
| Network cut to stall uploads | Heartbeat gap + spool depth reported in the heartbeat |

Alerts land in `integrity_alerts` and should page whoever owns clinical compliance. A session missing a
segment must be `quarantined`, not silently accepted.

### 4.3 Resistance to local interference

- **Watchdog service** (`LocalSystem`, `SERVICE_AUTO_START`, recovery actions = restart) supervises the
  user-session agent and reports every unexpected exit with the terminating process where obtainable.
  Note the constraint from the hardening plan: audio capture must stay in the **user session** — a
  session-0 service has no default audio endpoint — so the durable part and the capturing part are
  separate processes by necessity.
- **Doctors must be non-administrators** on their PCs. This is the single highest-leverage control in
  this entire document and it is an organisational decision, not a code change. Without it, the watchdog,
  the ACLs, and the service configuration are all bypassable.
- Remove the tray **Exit** item (`main.py:101,123-127`). Stopping collection becomes an admin action that
  writes an audit event with a reason.
- ACL `%ProgramFiles%\AIMScribe\` and the spool directory to `Administrators` + the service account. The
  spool is AES-256-GCM encrypted with a per-session key wrapped by DPAPI, so a local user cannot read or
  edit buffered audio even with file access.
- Sign the binaries (Authenticode) and have the watchdog verify the agent's signature before launch.

### 4.4 The legal counterpart

An always-on recorder that a doctor cannot stop is a strong evidentiary posture and a correspondingly
strong obligation. Two things must exist alongside it:

- **Patient consent captured at reception**, stored on the session (`consent_obtained`, `consent_method`,
  `consent_at`), with the agent refusing to open a session without it.
- **A visible recording indicator** — state-reflecting tray icon plus a banner in CMED. Covert recording
  of a medical consultation is the one variant of this system that is hard to defend anywhere.

Where a consultation genuinely must not be recorded, use a **supervised pause**: authorised, reason
recorded, appears in the audit log and the chain as an explicit gap. That satisfies R2 far better than an
unstoppable recorder, because an authorised gap is accounted for whereas a killed process is a hole.

---

## 5. R3 — clips stream as they are produced

```
capture thread ──▶ ring buffer ──▶ encoder/writer thread ──▶ spool segment (sealed, hashed)
                                                                    │
                                                          upload worker (ordered, 1 in flight)
                                                                    │
                          /segment/authorize → presigned PUT → MinIO → /segment/commit
```

Rules that make this reliable:

- **Never do file I/O on the capture thread.** Today `_save_clip` writes up to 12 MB synchronously inside
  `process_chunk` (`simple_splitter.py:130-169`), which runs on the PyAudio callback thread — frames are
  dropped at every segment boundary. Hand sealed buffers to a writer thread via `queue.Queue`.
- **Seal, hash, then upload.** A segment is committed to the chain the moment it is sealed, so its content
  is fixed before it ever leaves the PC.
- **Ordered, at-least-once, idempotent.** One upload in flight per session; `idempotency_key =
  (session_id, seq_no)`; the server treats a repeat commit with a matching sha256 as success and a repeat
  with a *different* sha256 as an integrity alert. The current key (`clip_uploader.py:117-121`) is a
  deterministic hash of the same tuple, which is fine — but it must be validated server-side.
- **Bounded retry with backoff, never drop.** `clip_uploader.py:163-176` currently logs
  `"Upload queue full, clip dropped"` — in this design a segment is never dropped, it stays in the spool.
- **Report spool depth in every heartbeat** so a doctor PC that has stopped draining is visible centrally.

Segment length stays 170–190 s with the silence-boundary split; that is a reasonable transcription
trade-off and is already implemented.

---

## 6. R4 — safe automatic deletion from the doctor's PC

Deleting the only copy of a clinical recording on the strength of an HTTP 200 is the riskiest line in the
current codebase (`file_forwarder.py:113-118`). Use a three-phase commit with a **signed purge receipt**:

```
Phase 1  agent  → PUT to MinIO                        (bytes durable in the landing zone)
Phase 2  agent  → POST /segment/commit {sha256}       server re-reads the object, recomputes sha256,
                                                      rejects on mismatch, writes the DB row
Phase 3  worker → archive to the sorted tree (§7),    fsync, re-verify sha256 from the archive copy,
                  mark session verified, then issue:
                  purge_receipt = Ed25519_sign(server_key, {session_id, seq_no, sha256, archived_at})
         agent  → verifies the signature against the pinned server key, THEN deletes the local file
```

Properties this gives you:

- Local deletion requires proof the archive copy exists **and hashes correctly** — not merely that a
  request succeeded.
- The receipt is signed, so an attacker who can reach the agent cannot forge "it's safe to delete" and
  destroy evidence. Deletion becomes an authorised operation, not a side effect.
- Every deletion is auditable: `segments.local_deleted_at` plus an audit event carrying the receipt.
- Failure is safe by construction — no receipt means the file stays, and the spool directory has a size
  cap that raises an alert rather than deleting the oldest data.

Retain the local copy of the *full* session for a configurable grace window (default 24 h) after the
receipt, so a corrupted archive is still recoverable. Purge segments immediately once archived, since the
full recording supersedes them.

---

## 7. R5 + R6 — archive layout and the database index

### 7.1 Directory tree

```
D:\AIMSLAB_AUDIO_STORAGE\
└── HOSP001\                                   ← hospital_id
    └── DR001\                                 ← doctor_id
        └── 2026-07-26\                        ← session date, hospital-local timezone
            ├── P12345_01J8FQ2K7X_0932-0947.ogg
            ├── P12345_01J8FQ2K7X_0932-0947.manifest.json
            ├── P67890_01J8FQ9M3B_1004-1021.ogg
            ├── P67890_01J8FQ9M3B_1004-1021.manifest.json
            └── _index.json                    ← per-day summary, regenerated by the worker
```

Filename: `{patient_ref}_{session_ulid}_{HHMM}-{HHMM}.ogg`

- `patient_ref` is there because you asked to find a patient's audio by browsing the date folder. It is
  acceptable **on this volume only** — BitLocker-encrypted, ACL'd to the ingest service account and the
  clinical-records group. It must never appear in a MinIO object key, a URL, a log line, or a metrics
  label; keys in the landing zone use the opaque ULID alone.
- `session_ulid` makes the name unique and sorts chronologically, so two visits by the same patient on the
  same day to the same doctor cannot collide.
- `manifest.json` travels with the audio: chain head, per-segment hashes, device id, app version, codec
  parameters, consent record, segment timestamps. The archive is then self-describing and independently
  verifiable if the database is ever lost.

Timezone rule: the date folder uses the **hospital's local date**, resolved from `hospitals.timezone`, not
the server's or UTC. Otherwise evening consultations scatter across two folders.

### 7.2 Storage tiers

| Tier | Location | Retention |
|---|---|---|
| Landing zone | MinIO bucket `aimscribe-landing` | 72 h, lifecycle-deleted after `verified` |
| Archive | `D:\AIMSLAB_AUDIO_STORAGE\` | Per policy (7 years per `ARCHITECTURE_DESIGN.md:346-353`) |
| Off-site | Encrypted replica (rclone → S3/R2 with object lock) | Matches archive |

A single self-hosted server holding the only copy of every consultation is the largest remaining risk in
this design. The off-site encrypted replica is not optional — treat it as part of R4.

### 7.3 Database schema (PostgreSQL)

```sql
CREATE TYPE session_status AS ENUM
  ('open','uploading','uploaded','archived','verified','purged','failed','quarantined');

CREATE TABLE hospitals (
    hospital_id   text PRIMARY KEY,                    -- 'HOSP001'
    name          text NOT NULL,
    timezone      text NOT NULL DEFAULT 'Asia/Dhaka',
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE doctors (
    doctor_id     text PRIMARY KEY,                    -- 'DR001'
    hospital_id   text NOT NULL REFERENCES hospitals,  -- primary affiliation
    name          text NOT NULL,
    bmdc_reg_no   text,
    active        boolean NOT NULL DEFAULT true
);

-- One row per installed agent. Identity is the mTLS client cert, not a self-declared id.
CREATE TABLE devices (
    device_id         uuid PRIMARY KEY,
    hospital_id       text NOT NULL REFERENCES hospitals,
    cert_fingerprint  bytea NOT NULL UNIQUE,
    tpm_pubkey        bytea NOT NULL,
    machine_name      text,
    os_version        text,
    app_version       text,
    enrolled_at       timestamptz NOT NULL DEFAULT now(),
    last_seen_at      timestamptz,
    revoked_at        timestamptz
);

CREATE TABLE sessions (
    session_id        text PRIMARY KEY,                -- ULID, also used in the filename
    hospital_id       text NOT NULL REFERENCES hospitals,
    doctor_id         text NOT NULL REFERENCES doctors,
    device_id         uuid NOT NULL REFERENCES devices,
    patient_ref       text NOT NULL,                   -- CMED patient id
    session_date      date NOT NULL,                   -- hospital-local; drives the folder
    opened_at         timestamptz NOT NULL,
    closed_at         timestamptz,
    duration_seconds  numeric(10,2),

    -- R6: resolve DB row -> file on disk
    archive_relpath   text UNIQUE,        -- 'HOSP001/DR001/2026-07-26/P12345_01J8..._0932-0947.ogg'
    archive_sha256    bytea,
    archive_bytes     bigint,

    -- integrity
    segment_count     integer NOT NULL DEFAULT 0,
    chain_head_hash   bytea,
    chain_verified_at timestamptz,

    -- consent (§4.4)
    consent_obtained  boolean NOT NULL DEFAULT false,
    consent_method    text,
    consent_at        timestamptz,

    status            session_status NOT NULL DEFAULT 'open',
    retention_until   date,
    legal_hold        boolean NOT NULL DEFAULT false,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ON sessions (hospital_id, doctor_id, session_date);
CREATE INDEX ON sessions (patient_ref, session_date DESC);
CREATE INDEX ON sessions (status) WHERE status <> 'verified';

CREATE TABLE segments (
    session_id        text NOT NULL REFERENCES sessions ON DELETE RESTRICT,
    seq_no            integer NOT NULL CHECK (seq_no > 0),
    object_key        text NOT NULL,                   -- opaque; no patient_ref
    bytes             bigint NOT NULL,
    duration_seconds  numeric(8,2) NOT NULL,
    sha256            bytea NOT NULL,
    prev_chain_hash   bytea,
    chain_hash        bytea NOT NULL,
    device_signature  bytea NOT NULL,
    rms_mean          real,                            -- blocked-mic detection
    captured_start_at timestamptz NOT NULL,
    captured_end_at   timestamptz NOT NULL,
    committed_at      timestamptz NOT NULL DEFAULT now(),
    archived_at       timestamptz,
    local_deleted_at  timestamptz,
    is_final          boolean NOT NULL DEFAULT false,
    PRIMARY KEY (session_id, seq_no)
);

-- Append-only, hash-chained. Revoke UPDATE/DELETE from the app role and enforce with a trigger.
CREATE TABLE audit_log (
    id           bigserial PRIMARY KEY,
    occurred_at  timestamptz NOT NULL DEFAULT now(),
    event_type   text NOT NULL,        -- session.open, session.close, segment.commit,
                                       -- purge.receipt, agent.killed, mic.muted, admin.stop, …
    actor_type   text NOT NULL,        -- device | doctor | service | admin
    actor_id     text,
    device_id    uuid REFERENCES devices,
    session_id   text REFERENCES sessions,
    detail       jsonb NOT NULL DEFAULT '{}',
    prev_hash    bytea,
    entry_hash   bytea NOT NULL
);
CREATE INDEX ON audit_log (session_id, occurred_at);
CREATE INDEX ON audit_log (event_type, occurred_at DESC);

CREATE TABLE integrity_alerts (
    id           bigserial PRIMARY KEY,
    raised_at    timestamptz NOT NULL DEFAULT now(),
    session_id   text REFERENCES sessions,
    device_id    uuid REFERENCES devices,
    alert_type   text NOT NULL,        -- chain_break | hash_mismatch | segment_gap |
                                       -- heartbeat_lost | mic_muted | silent_session | clock_skew
    severity     text NOT NULL,
    detail       jsonb NOT NULL DEFAULT '{}',
    resolved_at  timestamptz,
    resolved_by  text,
    resolution   text
);
```

Deliberate constraints: `ON DELETE RESTRICT` on `segments` so a session with segments cannot be deleted;
`archive_relpath UNIQUE` so two sessions cannot claim one file; `PRIMARY KEY (session_id, seq_no)` making
duplicate or renumbered segments impossible.

R6 in one query:

```sql
SELECT session_id, session_date, archive_relpath, duration_seconds, status
FROM   sessions
WHERE  patient_ref = 'P12345'
ORDER  BY session_date DESC, opened_at DESC;
-- archive_relpath is appended to the storage root to get the absolute path
```

Store `archive_relpath` **relative** to the root, never absolute — otherwise every row breaks the day the
volume is remounted or the archive moves.

---

## 8. Deployment on the AIMS LAB server

Self-hosting the backend brings obligations that a managed platform was covering:

- **Reachability.** Doctor PCs sit in 7–10 different hospital networks. Either a site-to-site/WireGuard
  VPN per hospital (preferred — the API is then never internet-facing), or a public TLS endpoint requiring
  **mTLS** so only enrolled devices can connect. Do not expose the API with bearer tokens alone.
- **TLS.** Real certificates and automated renewal. `config.py:60` currently uses `http://` — PHI audio
  must never cross a network in cleartext.
- **Backups.** Postgres PITR (WAL archiving) plus the encrypted off-site archive replica. Test a restore
  before go-live; an untested backup is not a backup.
- **Uptime.** UPS, RAID with monitored rebuilds, disk SMART alerting, and a documented failover. The
  agent's spool covers hours of outage, not days.
- **Monitoring.** Alert on: heartbeat loss per device, spool depth, `status <> 'verified'` older than 1 h,
  unresolved integrity alerts, archive free space, backup age.
- **Enrollment.** A one-time admin-authorised enrollment per PC issuing the mTLS cert and binding
  `device_id → hospital_id`. This is where a device's hospital is fixed, so it can never be self-declared
  the way `hospital_id` is today (`page.tsx:35-36`).

---

## 9. Capacity — why the codec choice matters here

20 doctors × 6 consulting hours × 22 days ≈ **2,640 doctor-hours per month**.

| Codec | Per hour | Per month | Per year | 7-year archive |
|---|---|---|---|---|
| WAV 32 kHz/16-bit (current) | 225 MB | 595 GB | 7.1 TB | ~50 TB |
| Opus 24 kbps mono @ 16 kHz | 10.8 MB | 28 GB | 342 GB | ~2.4 TB |

Same transcription accuracy — Whisper resamples to 16 kHz regardless, so the 32 kHz capture is discarded
before inference. On a self-hosted server with a 7-year retention obligation this is the difference
between a commodity disk array and a storage project.

---

## 10. Build order

| # | Work | Requirement |
|---|---|---|
| 1 | Lock down the local control plane: Origin/Host allowlist, signed CMED grants, delete legacy endpoints | prerequisite (`SECURITY_HARDENING_PLAN.md` §1–2) |
| 2 | Postgres schema + audit chain + `hospitals`/`doctors`/`devices` seed | R6 |
| 3 | Device enrollment, mTLS, TPM key generation | R2, §8 |
| 4 | Agent rewrite: capture → ring buffer → encrypted spool → Opus; writer thread off the capture path | R2, R3 |
| 5 | Segment chain + `/segment/authorize` / `/segment/commit` with server-side sha256 verification | R2, R3 |
| 6 | Ingest worker: bucket notification → archive tree → verify → metadata | R5, R6 |
| 7 | Signed purge receipts; agent deletes only on a verified receipt | R4 |
| 8 | Watchdog service, non-admin doctor accounts, remove tray Exit, signed MSI | R2 |
| 9 | Interruption detection + integrity alerts + operator dashboard | R2 |
| 10 | Consent capture and recording indicator | R2 / §4.4 |
| 11 | Off-site encrypted replica, PITR backups, restore drill | §7.2, §8 |
| 12 | Retire `file_forwarder.py` and the `aimslab-server` upload endpoints | R4, R5 |

Steps 1–2 unblock everything else and can proceed in parallel. Nothing before step 7 should run against
real patients with local deletion enabled — until the purge receipt exists, keep
`delete_after_forward = False` (`config.py:65`).

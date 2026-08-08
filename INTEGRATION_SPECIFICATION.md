# AIMScribe Integration Specification

The exact contract between the four parties. Protocol version **2**; agent
**2.3.1**.

| Party | Runs on | Talks to |
|---|---|---|
| **CMED web** | Vercel | Browser (page), agent (via the browser) |
| **Agent** | Consulting-room PC | CMED page (local WebSocket), backend (HTTPS) |
| **Backend** | Render | Agent, archive worker, administrators |
| **Archive worker** | AIMS LAB server | Backend only, outbound |

A mismatched `protocol_version` is rejected rather than guessed at.

---

## 1. CMED page → agent

### Transport

```
ws://127.0.0.1:5050/ws
```

The agent binds to loopback only. Two checks run **before** the WebSocket
handshake completes, and both close the socket with code `4403`:

| Check | Rule |
|---|---|
| `Origin` | Must appear **exactly** in `AIMS_ALLOWED_ORIGINS`. Wildcards are rejected at startup. A missing or literal `null` origin is refused — sandboxed iframes and non-browser clients both present it. |
| `Host` | Must appear in `AIMS_ALLOWED_HOSTS` (default `localhost:5050,127.0.0.1:5050,[::1]:5050`). This is what blocks DNS rebinding. |

Messages are JSON objects, capped at 64 KiB.

### Commands

| Command | Payload | Notes |
|---|---|---|
| `start` | `{ grant, session: { patient_name } }` | Requires a valid grant. Everything identifying comes from the grant, not from `session`. |
| `stop` | — | Closes with reason `doctor_stopped`. |
| `pause` | `{ reason, reason_detail, supervisor }` | Reason mandatory. Past `AIMS_PAUSE_SELF_AUTHORISE_SECONDS` (300 s) a supervisor name is required. |
| `resume` | — | |
| `status` | — | Returns the current status event. |
| `doctors` | — | Doctors seen at **this machine's hospital** before, as typing suggestions only. Grants nothing. |

### Replies and events

Commands are acknowledged separately from state changes. An acknowledgement goes
to the caller; events are broadcast to every connected tab.

```jsonc
{ "event": "ack",    "command": "start", "data": { … } }
{ "event": "status", "state": "recording", "sessionId": "…", … }
{ "event": "error",  "code": "unauthorised", "message": "…" }
```

| `code` | Raised by | Meaning |
|---|---|---|
| `refused` | `SessionError` | An expected refusal. Safe to show the doctor verbatim. |
| `unauthorised` | `GrantError` | Grant missing, malformed, expired, replayed, or unverifiable. Always renders as *"Authorisation failed. Reload CMED and try again."* |
| `internal` | anything else | Logged with a traceback; the doctor sees a generic message. |

> Because every `GrantError` collapses into one message, the agent log is the
> only place the real reason appears. See `OPERATIONS.md`.

### Local HTTP API

Same port, for support tooling rather than the page. All routes except `/health`
require `AIMS_LOCAL_API_KEY`.

| Route | Purpose |
|---|---|
| `GET /health` | Unauthenticated liveness probe. Reveals no session or patient data. |
| `GET /api/v1/session/status` | Current state |
| `GET /api/v1/doctors` | Who may record on this PC today |
| `POST /api/v1/session/stop` | |
| `POST /api/v1/session/pause` \| `/resume` | |
| `POST /api/v1/session/force-reset` | Clears a stuck state. Sealed audio is preserved and keeps uploading. |
| `GET /api/v1/diagnostics` | Everything support needs, with no patient identifiers |

There is deliberately **no local `start`**: a recording can only begin from a
signed grant.

---

## 2. The recording grant

Minted by `POST /api/recording-grant` on CMED. The private key
(`AIMS_GRANT_PRIVATE_KEY`) exists only in that server's environment; the agent
holds only the pinned public half at
`%PROGRAMDATA%\AIMScribe\keys\cmed_grant_pub.pem`.

### Claims

```jsonc
{
  "iss": "cmed",                       // AIMS_GRANT_ISSUER
  "aud": "aimscribe-recorder",         // AIMS_GRANT_AUDIENCE
  "sub": "DR001",                      // doctor_id
  "jti": "<uuid>",                     // single use
  "iat": 1785831622,
  "exp": 1785831682,                   // iat + 60 s
  "doctor_name": "",
  "hospital_id": "HOSP003",            // advisory only, see below
  "patient_ref": "1034GS6",
  "consent_obtained": true,
  "consent_method": "verbal_at_reception"
}
```

Algorithm is **EdDSA (Ed25519)** and nothing else. The verifier passes an
explicit algorithm list, which is what defeats `alg: none` and HMAC-confusion
attacks.

### Verification, in order

1. Signature, against the pinned key.
2. `iss`, `aud`, `exp`, `iat` — all required, with **5 seconds** of leeway.
3. `consent_obtained` must be truthy, else *"grant does not record patient consent"*.
4. `patient_ref` must be present.
5. `jti` must not have been seen before (in-process guard, pruned lazily).

**Lifetime is 60 seconds with 5 seconds of leeway.** A machine whose clock is
more than ~65 s out fails every grant it is handed. This is the single most
common cause of authorisation failures on a newly installed PC.

### What the grant does and does not decide

- **Doctor** and **patient** come from the grant. A consulting room runs two
  shifts on one laptop, so neither can belong to the machine.
- **Hospital** comes from the machine's enrolment. `hospital_id` in the grant is
  advisory: the controller compares it against the enrolment and raises an
  integrity alert on a mismatch rather than believing it.
- A grant with an empty `doctor_id` or `hospital_id` is still accepted by
  `verify_grant`; CMED's own route rejects an empty `doctor_id` with HTTP 400
  before it ever gets that far.

---

## 3. Agent → backend

Base: `https://<backend>/api/v2`. Every route requires `X-Device-Token`, issued
at enrolment and stored DPAPI-wrapped in `device.token` — deliberately **not**
in `device.json`, because it is a bearer credential.

### `POST /device/enroll`

The only unauthenticated route, since the device has no credential yet.

```jsonc
{
  "enrollment_token": "…",            // 16–256 chars, single use
  "device_pubkey": "<64 hex chars>",  // Ed25519 raw public key
  "machine_name": "DESKTOP-EH4I47M",
  "os_version": "Windows 11 …",
  "app_version": "2.3.1",
  "protocol_version": 2,
  "audio": { "sample_rate": 44100, "channels": 1, "sample_width": 2 }
}
```

Returns `device_id`, `hospital_id`, `doctor_id`, `device_token`.

The agent stores the **device token before the identity file**: if the process
dies between the two, the next start re-enrols rather than finding an identity
it holds no credential for. The used token is then deleted from disk.

The database stores only `sha256(token)`. A failure to reach the backend leaves
the token in place — a merely unreachable backend must not burn an
administrator's token.

### `POST /session/open`

```jsonc
{
  "session_id": "01KZ39EJN01QJPT3Z9ZFDRKCTY",   // ULID, minted on the PC
  "opened_at": "…", "doctor_id": "…", "hospital_id": "…",
  "patient_ref": "…", "consent_obtained": true, "consent_method": "…",
  "audio": { … }, "device_pubkey": "…",
  "genesis": { … }                               // first chain entry
}
```

The ULID is minted locally, so **recording starts even with the backend down.**

### `POST /segment/authorize` → `POST /segment/commit`

`authorize` issues a short-lived presigned PUT for exactly one segment
(`session_id`, `seq_no`, `bytes`, `sha256`). The agent uploads directly to
object storage, then commits:

```jsonc
{
  "session_id": "…", "seq_no": 1, "object_key": "…",
  "sha256": "…", "bytes": 123456, "duration_seconds": 41.7,
  "captured_start_at": "…", "captured_end_at": "…",
  "rms_mean": 0.02, "is_final": false,
  "chain_entry": { … }
}
```

> **The security property that matters most lives here.** `commit` re-reads the
> uploaded object from storage and recomputes its SHA-256 before storing
> anything. A client's claim about what it uploaded is never taken on trust.

### `POST /session/pause` · `/session/resume`

`{ session_id, chain_entry }` — appends a lifecycle entry.

### `POST /session/close`

```jsonc
{
  "session_id": "…", "closed_at": "…", "close_reason": "doctor_stopped",
  "duration_seconds": 214.4, "paused_seconds": 0, "segment_count": 5,
  "chain_head": "…", "chain_entry": { … }, "manifest": { … }
}
```

The whole chain is verified server-side at close. A broken chain quarantines the
session instead of archiving it.

### `GET /session/{id}/receipts`

Purge receipts the agent may act on. Empty until the worker has archived. The
agent verifies each Ed25519 signature, waits out `AIMS_PURGE_GRACE_HOURS`, and
only then deletes its local copy.

### `POST /heartbeat`

Every 30 s: state, spool bytes, spool pressure, pending segments.

### Retry semantics

Backoff is `2, 8, 30, 120, 600` seconds. A retried chain entry is verified in
full — payload hash, entry hash, device signature — against its *own*
`prev_hash`, which runs every check except the comparison against the stored
head. That is the only check a legitimate retry can fail, because the head has
moved past the entry precisely because it was already accepted.

---

## 4. Archive worker → backend

Authenticated with `X-Worker-Key`. **Outbound only** — the worker listens on no
port and accepts no connections, and holds no bucket credentials; it receives
short-lived presigned URLs for exactly the objects it needs.

```
1. GET  /api/v2/archive/pending      sessions closed, verified, not archived
2. download each segment             verify sha256 against the manifest
3. join into one WAV                 atomic write, then fsync
4. re-read from disk and hash        proves the bytes actually landed
5. write manifest.json and _index.json
6. POST /api/v2/archive/complete     { session_id, archive_relpath, sha256, bytes }
                                     → backend issues the purge receipts
```

A session is reported complete only after step 4. Any failure leaves it pending,
the agent keeps its local audio, and the next pass retries.

### Archive layout

```
<AIMS_ARCHIVE_ROOT>/<HOSPITAL>/<DOCTOR>/<YYYY-MM-DD>/<CONSULTATION>/<CONSULTATION>.wav
```

The date is the **hospital's local date**, resolved through its configured
timezone. Using UTC would file an evening consultation at UTC+6 under the
previous day — permanently, because `session_date` decides the folder once.

---

## 5. Administration

All require `X-Admin-Key`.

| Route | Purpose |
|---|---|
| `POST /admin/hospital` | Create or rename. Overwrites `name` and `timezone`; **never** changes `hospital_id`. |
| `POST /admin/doctor` | Record a doctor's real name for reports. Grants nothing. |
| `POST /admin/enrollment-token` | Mint a single-use token. `ttl_hours` is `ge=1, le=720`. |
| `POST /admin/device/{id}/revoke` | Immediate; `require_device` then rejects it. |
| `GET /admin/alerts` | Open integrity alerts — the operator's queue. |
| `GET /doctors?hospital_id=` | Device-authenticated; feeds the agent's `doctors` command. |

---

## 6. Identifier rules

Identifiers become folder names on the archive volume, so they are kept boring:

```
^[A-Za-z0-9_-]{1,64}$        CMED (assertSafeIdentifier)
^[A-Za-z0-9-]{1,64}$         backend filename component (_NAME_SAFE)
```

Anything else and the clip goes unnamed rather than letting a path separator or
a fragment into the archive tree.

---

## 7. Audio contract

| Property | Value |
|---|---|
| Format | WAV PCM, 44.1 kHz, mono, 16-bit |
| Rate | ~318 MB per hour |
| Clip length | 30–60 s, cut on 3 s of quiet (RMS < 320), 15 s grace before a forced cut |
| Spool | AES-256-GCM, DPAPI-wrapped key, 40 GB (~3 weeks) |

Changing sample rate, channel count or sample width changes the archive
contract. The backend validates `8000 ≤ sample_rate ≤ 192000`, `1 ≤ channels ≤ 2`
and rejects anything but 16-bit at the agent.

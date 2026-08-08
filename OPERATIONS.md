# AIMScribe Operations Runbook

Day-to-day procedures for running the fleet. For how the system works, see
[`README.md`](README.md) and [`ARCHITECTURE.md`](ARCHITECTURE.md); for the exact
wire contract, see
[`INTEGRATION_SPECIFICATION.md`](INTEGRATION_SPECIFICATION.md).

Everything here is done from an **administrator's** machine. Nothing in this
document is ever run on a consulting-room PC — those receive an installer and
nothing else.

---

## The fleet

| `hospital_id` | Clinic | Notes |
|---|---|---|
| `HOSP001` | Karail | |
| `HOSP002` | Mirpur | |
| `HOSP003` | Dholpur | |
| `HOSP004` | Shyampur | |

`hospital_id` is the top-level folder name in the archive. **The display name
may be changed at any time; the id must never change.** Renaming a clinic is a
one-line operation (below) and affects nothing else. Changing an id would orphan
every archived recording and every enrolled device under it.

---

## Enrol a new consulting-room PC

Enrolment exists for exactly one reason: **an unregistered laptop cannot run the
software.** It does not decide who the doctor is.

### 1. Mint a token

One row per **laptop**, not per doctor. A token is consumed on first use, so a
room with two laptops needs two rows.

Write a **new, dated** CSV rather than editing an existing one — these files are
read as the register of what is deployed:

```csv
hospital_id,hospital_name,room,doctor_id,doctor_name
HOSP003,Dholpur,Room 1,,
HOSP003,Dholpur,Room 2,,
```

`doctor_id` and `doctor_name` are optional and only label the paperwork. Leave
them blank unless a machine has one regular user.

From the **backend** repository:

```powershell
$env:AIMS_TOKEN_TTL_HOURS = "720"      # 30 days; 720 is the hard maximum
python scripts\mint_enrolment_tokens.py scripts\laptops_add_20260804.csv
```

`AIMS_ADMIN_KEY` is read from the environment, or from the backend's `.env` if
not set. The default TTL is 72 hours, which is usually too short when the
machines are in another district — 720 hours is the ceiling enforced by the API
(`ttl_hours: int = Field(72, ge=1, le=720)`).

This writes `enrolment_<timestamp>/` containing one instruction sheet per PC
plus a `register.csv` that deliberately contains **no tokens**.

> The database stores only `sha256(token)`. **The plaintext token exists nowhere
> but that generated sheet.** If it is lost, mint a new one — it cannot be
> recovered. Delete the folder once the machines are installed.

### 2. Install on the PC

Run `AIMScribeSetup.exe` as administrator. Three fields; the first two are
pre-filled:

| Field | Value |
|---|---|
| Backend URL | `https://aimscribe-backend-render.onrender.com` |
| CMED web address | `https://aim-scribe-exe.vercel.app` |
| Enrolment token | paste from the sheet |

The installer writes `.env`, installs the pinned public keys, registers a logon
task, and stages the token at
`%PROGRAMDATA%\AIMScribe\state\enrollment.token`. The agent consumes it on first
start and deletes it.

### 3. Verify

Open the CMED address on that PC. The page should show the hospital id and say
the PC is ready. Then confirm server-side that the device appears:

```sql
SELECT device_id, hospital_id, machine_name, app_version, enrolled_at
FROM devices ORDER BY enrolled_at DESC LIMIT 5;
```

### Re-installing an already-enrolled PC

**Leave the token box empty.** The machine keeps its existing identity in
`device.json`. A second token is not consumed and not needed — once a device has
an identity, `ensure_enrolled()` returns it and never looks at a pending token.

A token is only needed again if the device key was destroyed (disk re-image,
wiped `keys` folder), because the server still holds the old public key and the
old identity is no longer valid.

---

## Add a new clinic

There is no separate "create clinic" step. Minting a token for a
`hospital_id` that does not exist creates it. Put the real clinic name in
`hospital_name` — it is what appears in reports.

Currently unmapped clinics that will need ids before they record anything:
Naryanganj, Ershadnagar, and Amader Susastho.

---

## Rename a clinic

Display name only. `hospital_id` is untouched, so **no token, device, or archive
path changes.**

```
POST /api/v2/admin/hospital
X-Admin-Key: <admin key>

{ "hospital_id": "HOSP001", "name": "Karail", "timezone": "Asia/Dhaka" }
```

`upsert_hospital` overwrites `name` and `timezone` on this path. Existing
enrolled devices keep working without reinstalling.

---

## Revoke a device

For a lost or decommissioned laptop:

```
POST /api/v2/admin/device/{device_id}/revoke
X-Admin-Key: <admin key>
```

The device token stops authenticating immediately — `require_device` rejects any
device with `revoked_at` set.

---

## Diagnosing failures

### "Authorisation failed. Reload CMED and try again."

This message comes from the **agent**, in the WebSocket command handler, and it
means only one thing: `verify_grant()` raised. It has **nothing to do with the
enrolment token** — by the time this appears, the PC is already enrolled and
talking to CMED.

The grant lives **60 seconds**, with 5 seconds of leeway. Causes, in the order
worth checking:

| Cause | How it looks | Fix |
|---|---|---|
| **PC clock wrong** | Most common on a freshly installed machine. More than ~65 s behind CMED gives `ImmatureSignatureError`; more than ~65 s ahead gives `ExpiredSignatureError`. | Settings → Time & language → set the timezone to **(UTC+06:00) Dhaka** and press **Sync now**. |
| **Grant key missing** | The agent logs `Grant key unavailable` as CRITICAL at startup. | Check `%PROGRAMDATA%\AIMScribe\keys\cmed_grant_pub.pem` exists; reinstall if not. |
| **Grant replayed** | `grant has already been used`. A single `jti` is accepted once. | Reload the CMED page to get a fresh grant. |

All three collapse into the same doctor-facing message, so **read the log** —
it records the real reason:

```
C:\ProgramData\AIMScribe\logs\agent.log
```

Open it in Notepad; look for `Command start rejected:` near the failure time.

To confirm the shipped key still matches CMED's signing key, request a grant
from `POST /api/recording-grant` and verify it against
`recorder/keys/cmed_grant_pub.pem` with `algorithms=["EdDSA"]`, `issuer="cmed"`,
`audience="aimscribe-recorder"`. If that verifies, the key is fine and the fault
is on the machine.

### "This PC is not enrolled"

The token was not accepted. Almost always: mistyped, already used on another
machine, or expired. Check whether it was consumed:

```sql
SELECT hospital_id, created_at, expires_at, used_at, device_id
FROM enrollment_tokens WHERE token_sha256 = $1;   -- bytea, not hex
```

`used_at IS NOT NULL` means it worked and the device is enrolled — the problem
is elsewhere. Mint a new token if it is genuinely unused and expired.

### The page loads but Start does nothing

The CMED address must match `AIMS_ALLOWED_ORIGINS` **exactly**. Vercel preview
URLs are rejected, which is the point — it is what stops a stray page recording
a patient.

### Recording works but nothing uploads

Normal on a poor connection. Audio is held encrypted on the PC — roughly 135
hours of it — and uploads when the network recovers. Nothing is deleted until
the hospital's archive holds a verified copy.

---

## Useful queries

```sql
-- Who is enrolled where
SELECT hospital_id, count(*) FROM devices
WHERE revoked_at IS NULL GROUP BY hospital_id ORDER BY hospital_id;

-- Tokens still live
SELECT hospital_id, created_at, expires_at FROM enrollment_tokens
WHERE used_at IS NULL AND expires_at > now() ORDER BY hospital_id;

-- Doctor activity, observed rather than configured
SELECT * FROM v_doctor_activity;
SELECT * FROM v_doctors;

-- The operator's queue
SELECT * FROM integrity_alerts WHERE resolved_at IS NULL ORDER BY raised_at DESC;
```

A doctor in `v_doctors` with `devices_enrolled = 0` is a leftover from v1, when
the browser could name anyone.

---

## Deleting things safely

Two rules, learned the hard way:

1. **`audit_log` cannot be deleted from.** A trigger raises on `UPDATE` and
   `DELETE`. That is deliberate: the record that a session existed has to
   outlive the session rows. Exclude it from any cleanup, or the whole
   transaction rolls back and nothing is deleted.

2. **Move audio aside; do not delete it.** Confidence that a recording is test
   data is not the same as proof. Move it to a dated folder under the archive
   root and delete it later, once someone has actually looked.

Child rows have foreign keys without cascades. Rather than hard-coding a delete
order that a later migration would invalidate, delete inside a savepoint and
retry the ones a constraint still blocks until the set stops shrinking.

---

## Still outstanding

- Authenticode-sign `AIMScribe_Agent.exe` and `AIMScribeSetup.exe`.
- Rotate the hardcoded webhook secret.
- Back up `D:\AIMSLAB_AUDIO_STORAGE`.
- Real-audio verification of the 30–60 s splitter; relax the 3 s silence hold if
  clips consistently hit the 75 s ceiling.

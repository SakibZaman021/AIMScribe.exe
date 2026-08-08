# AIMScribe Demo Setup

Setting up a demonstration or evaluation machine. **This is not the procedure
for a clinical PC** — a consulting-room machine gets `AIMScribeSetup.exe` and
nothing else. See [`OPERATIONS.md`](OPERATIONS.md) for that.

---

## Option A — demonstrate the real thing (recommended)

The installer is the demo. It takes about two minutes and exercises the same
code path a clinic uses.

1. Ask the AIMScribe team for a **one-time enrolment token**.
2. Run `AIMScribeSetup.exe` as administrator on the demo PC.
3. Fill in three fields — the first two are pre-filled:

   | Field | Value |
   |---|---|
   | Backend URL | `https://aimscribe-backend-render.onrender.com` |
   | CMED web address | `https://aim-scribe-exe.vercel.app` |
   | Enrolment token | paste from the sheet |

4. Open the CMED address in the browser **on that PC**. It should show the
   hospital id and report the PC ready.

Nothing else is installed and no terminal is needed. A token is consumed on
first use, so a second demo machine needs a second token.

---

## Option B — run from source

For development machines only.

### Prerequisites

- Windows with a working microphone
- Python 3.12
- Node.js 18+

### 1. Generate local signing keys

```powershell
cd recorder
pip install -r requirements.txt
python scripts\dev_keys.py
```

This creates the CMED grant and purge-receipt key pairs. Without them the agent
refuses to start recording — `Config.validate()` reports the missing pinned keys
and the tray shows the reason.

### 2. Configure the agent

Copy `recorder\.env.example` to `recorder\.env`. The settings that must be right
for a local demo:

```env
AIMS_BACKEND_URL=http://localhost:6000
AIMS_ALLOWED_ORIGINS=http://localhost:3000
AIMS_LOCAL_API_KEY=<any non-placeholder value>
AIMS_ALLOW_PLAINTEXT_KEYSTORE=true
```

`AIMS_ALLOWED_ORIGINS` must match the CMED origin **exactly** — no wildcards,
no trailing slash. The agent refuses the WebSocket handshake from anything else,
which is the check that stops a stray page recording a patient.

`AIMS_ALLOW_PLAINTEXT_KEYSTORE=true` is acceptable on a development box and
**must never** be set on a clinical PC; it leaves private keys un-wrapped.

### 3. Configure CMED

Copy `cmed-web\.env.local.example` to `.env.local` and set at minimum:

```env
NEXT_PUBLIC_BACKEND_URL=http://localhost:6000
NEXT_PUBLIC_RECORDER_WS=ws://localhost:5050/ws
AIMS_GRANT_PRIVATE_KEY=<the private key from dev_keys.py>
```

Verify with `GET /api/config-check`, which reports which variables are set
without ever returning a value.

### 4. Run

Two terminals:

```powershell
cd recorder ; python main.py
```

```powershell
cd cmed-web ; npm install ; npm run dev
```

Then open `http://localhost:3000`.

### 5. Enrolling the dev agent

The agent still needs an identity. Either mint a token against a backend you
control (see `scripts/mint_enrolment_tokens.py` in the backend repository), or
write one to `%PROGRAMDATA%\AIMScribe\state\enrollment.token` before first
start.

An unenrolled agent starts, shows its tray icon, and refuses to record. That is
deliberate — it is far easier to diagnose than a silent failure, and much safer
than filing sessions under a guessed hospital.

---

## Using it

1. **Reception** — enter patient id, name, age, gender and any screening data.
2. **Doctor** — confirm the patient has consented, choose the doctor, press
   **Start Consultation**. Recording does **not** start automatically; it
   requires a signed grant, and consent is a precondition rather than a field to
   fill in afterwards.
3. **During** — transcripts and extracted fields begin appearing once two clips
   have been processed, so structure builds while the consultation is still
   going.
4. **Stop** — the final extraction runs against the full transcript. Review and
   print.

Pausing needs a reason. Past five minutes it also needs a supervisor's name.
Both are written into the session's hash chain, so the gap in the audio is
accounted for.

---

## Troubleshooting

| Symptom | Cause |
|---|---|
| *"Authorisation failed. Reload CMED and try again."* | The grant was rejected. Most often the PC's clock is more than ~65 s out — the grant lives 60 s. See `OPERATIONS.md`. |
| *"This PC is not enrolled"* | No identity and no usable token. Mint a fresh one. |
| Page loads, **Start** does nothing | The browser origin is not in `AIMS_ALLOWED_ORIGINS`, so the WebSocket was refused. |
| Recording works, nothing uploads | Expected on a poor link. Audio is spooled encrypted — about 135 hours' worth — and uploads on recovery. Nothing is deleted until the archive holds a verified copy. |
| No transcript | Needs two clips (~1 minute of speech). Check the backend worker is running. |

The agent's log is at `C:\ProgramData\AIMScribe\logs\agent.log` and records the
real reason behind the doctor-facing messages. Identifiers are redacted.

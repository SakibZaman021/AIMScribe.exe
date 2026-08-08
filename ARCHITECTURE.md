# AIMScribe Architecture

How the system is built and why. This describes what is **deployed today** —
agent 2.3.1, protocol 2 — not an aspiration.

For procedures see [`OPERATIONS.md`](OPERATIONS.md); for the wire contract see
[`INTEGRATION_SPECIFICATION.md`](INTEGRATION_SPECIFICATION.md); for what the
system enforces see [`SECURITY.md`](SECURITY.md).

---

## 1. Components

| Component | Repository | Deployed to | Inbound ports |
|---|---|---|---|
| Tray agent | `recorder/` | Consulting-room PCs | `127.0.0.1:5050` only |
| CMED web | `cmed-web/` | Vercel | 443 |
| Backend API | backend `src/` | Render | 443 |
| Archive worker | backend `archive_worker/` | AIMS LAB server | **none** |
| Database | — | Neon (managed Postgres) | — |
| Transit storage | — | Cloudflare R2, S3 API, bucket `aimscribe-audio`, region `auto` | — |
| Archive volume | — | `D:\AIMSLAB_AUDIO_STORAGE` | — |
| AI | — | Azure OpenAI | — |

The AIMS LAB server, which holds the actual patient audio, has **no inbound
attack surface at all**. It pulls. That is the single most important structural
decision in the design.

> Cloudflare R2 is reached through the S3-compatible client, so its settings are
> still named `MINIO_*` in the backend configuration. `MINIO_REGION` must be
> `auto` for R2 — the region is part of the SigV4 signature, and a mismatch
> fails every presigned request with `SignatureDoesNotMatch`.

---

## 2. Trust model

Three principals, three credentials, no shared secrets between them:

| Principal | Credential | Scope |
|---|---|---|
| Agent | `X-Device-Token` (issued at enrolment, DPAPI-wrapped on disk) | Its own sessions only |
| Archive worker | `X-Worker-Key` | Archive handshake |
| Administrator | `X-Admin-Key` | Hospitals, doctors, tokens, revocation |

Plus two signing keys, each held by exactly one party:

| Key | Private half | Public half | Signs |
|---|---|---|---|
| CMED grant | CMED server env | Pinned on every agent | Recording grants |
| Purge receipt | Backend env | Pinned on every agent | Proof the archive holds a verified copy |
| Device key | The PC, DPAPI-wrapped | Registered at enrolment | Every chain entry |

The device key never leaves the machine. If it is regenerated — a wiped `keys`
folder, a restored disk image — the stored identity is refused, because the
server still holds the previous public key, and the machine must re-enrol.

### Why the browser is never trusted for identity

In v1 the page typed its own hospital into a text box, and the archive tree was
built from that string. A typo filed a consultation under a hospital that did
not exist. Now:

- **Hospital** comes from enrolment. The browser cannot express it.
- **Doctor** comes from a CMED-signed grant, per consultation, because a room
  runs two shifts on one laptop.
- **Patient** comes from the same grant.

A page the doctor happens to visit cannot start a recording, because it cannot
mint a grant and the origin allowlist refuses its WebSocket handshake.

---

## 3. Session lifecycle

```
        ┌──────────┐  grant verified   ┌───────────┐
        │   idle   │──────────────────►│ recording │◄──┐
        └──────────┘                   └───────────┘   │ resume
             ▲                            │      │     │
             │ close entry signed         │      ▼     │
             │                            │  ┌────────┐│
        ┌──────────┐                      │  │ paused ├┘
        │  closed  │◄─────────────────────┘  └────────┘
        └──────────┘   stop
```

Every transition writes a signed entry into the hash chain. A pause is a
first-class state with a mandatory reason, and past five minutes a named
supervisor — so a gap in the audio is *explained* rather than unaccounted for.

`close_reason` records how a session ended: `doctor_stopped`,
`stopped_from_tray`, `superseded_by_new_patient`. Abnormal closes raise an
integrity alert and surface in `v_abnormal_closes`.

---

## 4. The hash chain

Each session carries an append-only chain, keyed by `(session_id, entry_no)`:

```
entry_no  type      payload                        prev_hash → entry_hash
────────────────────────────────────────────────────────────────────────
   0      open      doctor, hospital, patient,     ∅        → H₀
                    consent, audio spec
   1      segment   seq_no, sha256, bytes,         H₀       → H₁
                    duration, captured times
   2      pause     reason, supervisor             H₁       → H₂
   3      resume                                   H₂       → H₃
   4      segment   …                              H₃       → H₄
   5      close     counts, duration, chain head   H₄       → H₅
```

Every entry is signed by the device key. `entry_hash` commits to the payload
hash **and** to `prev_hash`, so deleting, reordering or substituting any entry
breaks every entry after it.

Verification happens **on the server at close**, never on the machine that
produced the chain. A broken chain quarantines the session — it is not archived,
and `quarantine_reason` records why.

Three independent re-verifications guard the audio itself:

| Where | What is re-checked | Defeats |
|---|---|---|
| `/segment/commit` | Backend re-reads the object from R2 and recomputes SHA-256 | A client lying about what it uploaded |
| Archive worker step 2 | Each downloaded segment against the manifest | Corruption in transit or at rest |
| Archive worker step 4 | The joined WAV re-read from disk after fsync | Bytes that never actually landed |

Only after the third does the backend issue purge receipts.

### Two implementations, one specification

The chain is built by `recorder/core/crypto.py` here and verified by
`src/integrity.py` in the backend repository. Every constant and hashing rule
must agree byte for byte, or valid chains are rejected and the scheme becomes
noise — and the two repositories are never checked out together, so a
one-character divergence would be invisible in review.

That agreement is pinned by golden vectors rather than by discipline.
`recorder/tests/wire_vectors.json` holds fixed inputs and the exact outputs the
format requires; an identical copy lives in the backend. Each side replays them
against its own code, so either detects its own drift alone:

- **Here**, `tests/test_wire_compatibility.py` rebuilds a full signed session
  from a fixed key and requires every entry to come out byte for byte identical.
  Ed25519 is deterministic, so signatures are pinned too.
- **In the backend**, the same vectors must verify — whole chain and per entry —
  and its `ReceiptSigner` must reproduce the reference signature exactly. If it
  did not, every agent would reject every receipt and silently never delete its
  local audio.

Both pin the vectors' SHA-256, and both repositories mark the file `-text` in
`.gitattributes` so line-ending conversion cannot change that hash on checkout.

Regenerating the vectors redefines the protocol and is a two-repository change:

```powershell
python scripts\gen_wire_vectors.py tests\wire_vectors.json
```

---

## 5. Storage tiers

```
   PC spool                R2 (transit)              AIMS LAB archive
   ─────────               ────────────              ────────────────
   AES-256-GCM             presigned PUT             plain WAV, sorted tree
   DPAPI-wrapped key       short-lived URLs          manifest.json per session
   40 GB ≈ 3 weeks         deleted after archive     retention + legal hold
   deleted on receipt
   + 24 h grace
```

### Why audio is deleted only against a receipt

An HTTP 200 proves a request was accepted, not that a durable copy exists. Local
audio is therefore deleted only against an Ed25519 purge receipt, which is
issued only after the archive worker has re-read the joined file from disk and
matched its hash. **If the archive is lost, no receipt is issued and nothing is
deleted.**

A further 24-hour grace period runs after the receipt verifies, as a safety net
against a receipt that was correct but an archive that later fails.

### Capacity

At 44.1 kHz mono 16-bit:

| Quantity | Value |
|---|---|
| Bitrate | 88.2 KB/s |
| Per hour | ~318 MB |
| Per consultation (12 min) | ~64 MB |
| 40 GB spool | ~135 hours of audio ≈ 3 weeks of backend downtime |
| 25 laptops × 6 h/day | ~48 GB/day arriving at the archive |

The archive worker refuses to write below `AIMS_DISK_HEADROOM_BYTES` (20 GB by
default), leaving sessions pending rather than filling the volume.

---

## 6. Data model

Live schema, `public`. Protocol-2 tables first:

| Table | Holds |
|---|---|
| `hospitals` | `hospital_id` (**immutable**, the archive folder name), display name, timezone |
| `doctors` | `doctor_id`, `hospital_id`, `full_name`, `active` — a directory for reports; grants nothing |
| `devices` | One row per enrolled PC: `device_id`, `hospital_id`, `tpm_pubkey`, machine facts, `revoked_at` |
| `enrollment_tokens` | `token_sha256` (**bytea, never the plaintext**), `hospital_id`, `expires_at`, `used_at`, `device_id` |
| `sessions` | ULID id, device, doctor, patient, consent, times, `close_reason`, `manifest`, quarantine, `archive_relpath`/`archive_sha256`/`archive_bytes`, `retention_until`, `legal_hold` |
| `chain_entries` | `(session_id, entry_no)`, type, payload, hashes, signature |
| `segments` / `clips` | Per-clip metadata; object keys, hashes, durations |
| `purge_receipts` | Signed proofs the agent may act on |
| `integrity_alerts` | `alert_type`, `severity`, `detail`, `resolved_at` — the operator's queue |
| `audit_log` | **Append-only**, hash-linked (`prev_hash`/`entry_hash`) |
| `used_grants` | Server-side `jti` replay record |
| `api_keys` | Hashed keys with scope and expiry |

AI pipeline tables: `patients`, `health_screenings`, `transcripts`,
`ner_results`, `previous_visits`, `prescription_data`, `doctor_reviews`.

Reporting views: `v_doctors`, `v_doctor_activity`, `v_doctor_register`,
`v_audio_files`, `v_abnormal_closes`, `v_session_pauses`, `patient_recordings`.

> `patient_recordings` is a **view**, not a table.
> `playing_with_neon` is a leftover sample table from provisioning and can be
> dropped.

### The append-only audit log

```sql
CREATE TRIGGER audit_log_no_change
  BEFORE UPDATE OR DELETE ON audit_log …   -- raises
```

`audit_log is append-only; DELETE is not permitted`. This is deliberate and load
bearing: the record that a session was opened, archived and later removed has to
outlive the session rows themselves. Any cleanup that includes `audit_log` will
roll back its entire transaction and delete nothing.

Child tables have foreign keys **without** cascades. The safe way to delete a
set of sessions is to attempt each child table inside a savepoint and retry the
ones a constraint still blocks, until the blocked set stops shrinking — that
settles the order from the live constraint graph instead of hard-coding one a
later migration would silently invalidate.

---

## 7. The AI pipeline

Independent of the integrity path: audio reaches transcription through the same
committed segments, but a failure here never affects archival.

```
segment committed
      │
      ▼
Redis queue ──► worker ──► Azure OpenAI gpt-4o-transcribe
                              │   Bengali, diarised: [ডাক্তার] [রোগী] [রোগীর সাথী]
                              ▼
                         transcripts (cumulative per session)
                              │
                   ≥ 2 clips, or final
                              ▼
                    NER: Azure OpenAI gpt-5.2-chat
                    9 extractors in parallel
                              ▼
                         ner_results ──► CMED dashboard ──► prescription
```

The nine extractors are chief complaints, symptoms, diagnosis, medications,
tests, examination, follow-up, advice and referral. Patient baseline and
previous medications are fetched for context and cached in Redis for an hour,
which is what makes "continue the same medicine" work.

NER runs from two clips onward so the doctor sees structure building while the
consultation is still going, then again at close with the full transcript.

---

## 8. Failure behaviour

| What fails | What happens |
|---|---|
| Backend unreachable | Recording continues. The ULID is minted locally. Segments queue in the encrypted spool; upload resumes on recovery. |
| Spool reaches 50% / 80% | Tray warns, then warns critically. Recording continues. |
| Object storage rejects a commit | Segment stays pending and retries with backoff `2, 8, 30, 120, 600` s. |
| Hash mismatch at commit | Session quarantined. Not archived. Alert raised. |
| Chain broken at close | Session quarantined. **Never repaired by hand** — a chain that can be hand-repaired proves nothing. Fix the code path that broke it. |
| Archive worker down | Sessions stay pending. No receipts issued, so no PC deletes anything. |
| Archive volume lost | No receipts. Every PC retains its local copy. |
| PC clock wrong by > 65 s | Every grant fails. Recording cannot start. See `OPERATIONS.md`. |
| Device key regenerated | Identity refused; the PC must be re-enrolled. |

The recurring principle: **degrade toward keeping audio, never toward deleting
it.**

---

## 9. Known gaps

- `AIMScribe_Agent.exe` and `AIMScribeSetup.exe` are not yet Authenticode-signed.
- The webhook secret is hardcoded and should be rotated.
- `D:\AIMSLAB_AUDIO_STORAGE` has no backup.
- v1 routes on the backend remain unauthenticated; only `/api/v2` requires a
  credential.
- mTLS between agent and backend is supported by configuration but not deployed.

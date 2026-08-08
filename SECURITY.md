# Security Policy

AIMScribe records clinical consultations. The threat that matters is not an
outage — it is a recording that is silently wrong, missing, or attributed to the
wrong doctor, hospital or patient.

This document states what the system enforces, what it does not, and how to
report a flaw. For how it is built, see [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## Reporting a vulnerability

Report privately to the AIMS LAB team. **Do not open a public issue**, and never
include patient identifiers, tokens, keys or recordings in a report.

Say what you did, what happened, and what you expected. You should get an
acknowledgement within a few working days.

---

## Supported versions

| Version | Supported |
|---|---|
| Agent 2.3.x (protocol 2) | Yes |
| Agent 2.0 – 2.2 (protocol 2) | Security fixes only; upgrade |
| Anything protocol 1 | **No.** Superseded and structurally insecure |

Protocol 1 let the browser type its own hospital into a text box and build the
archive path from it, had no authentication on any route, cut 170–190 s clips at
32 kHz, and forwarded whole recordings to an unauthenticated endpoint on the
AIMS LAB server. None of it is supported and none of it may be redeployed.

---

## What the system enforces

Each property below has a regression test. Run `python -m pytest` in `recorder/`.

### Authorisation to record

| Property | Test |
|---|---|
| Only an `EdDSA` grant is accepted; `alg: none` is refused | `test_unsigned_alg_none_token_is_rejected` |
| A grant signed by any other key is refused | `test_grant_signed_by_another_key_is_rejected` |
| Expired, wrong-issuer and wrong-audience grants are refused | `test_bad_grants_are_rejected` |
| A grant is single use — a replayed `jti` is refused | `test_grant_is_single_use` |
| No grant means no recording | `test_missing_grant_is_rejected` |

Grants live **60 seconds** with 5 seconds of leeway, so a captured one is
worthless before it could be replayed by hand.

The agent's WebSocket accepts only exact configured origins and hosts. A missing
or literal `null` origin is refused — sandboxed iframes and non-browser clients
both present it, and neither should drive a recording. Wildcards are rejected at
startup, and there is deliberately **no local `start` route**: a recording can
begin only from a signed grant.

### Evidence that audio is intact

| Property | Test |
|---|---|
| Deleting a segment breaks the chain | `test_deleting_a_segment_is_detected` |
| Reordering segments breaks the chain | `test_reordering_segments_is_detected` |
| Substituting audio breaks the chain | `test_substituting_audio_is_detected` |
| Recomputing hashes after an edit still fails without the device key | `test_recomputing_hashes_after_edit_still_fails_without_the_key` |
| An unsigned entry is refused | `test_unsigned_entry_is_rejected` |
| A pause is part of the chain, so a gap is accounted for | `test_pause_is_part_of_the_chain` |
| Clips reassemble into the original recording byte for byte | `test_the_clips_reassemble_into_the_original_recording_byte_for_byte` |

The chain is verified **on the server at close**, never on the machine that
produced it. A broken chain quarantines the session rather than archiving it.

**A quarantined session is never repaired by hand.** A chain that can be
hand-repaired proves nothing; fix the code path that broke it.

### Audio at rest on the PC

| Property | Test |
|---|---|
| Segments are encrypted on disk (AES-256-GCM, DPAPI-wrapped key) | `test_segment_is_encrypted_on_disk` |
| A tampered spool file fails authentication | `test_tampered_spool_file_fails_authentication` |
| A pending segment cannot be purged | `test_pending_segment_cannot_be_purged` |
| A committed but unreceipted segment cannot be purged | `test_committed_segment_cannot_be_purged` |
| Only a receipted segment is purged | `test_receipted_segment_is_purged` |
| The session id does not leak the patient id | `test_session_id_does_not_leak_patient_id` |

### Deletion requires proof, not an HTTP 200

| Property | Test |
|---|---|
| A valid receipt authorises deletion | `test_valid_receipt_authorises_deletion` |
| A receipt for a different segment is refused | `test_receipt_for_a_different_segment_is_rejected` |
| A receipt whose hash does not match is refused | `test_receipt_with_mismatched_hash_is_rejected` |
| A forged receipt is refused | `test_forged_receipt_is_rejected` |
| A tampered receipt payload is refused | `test_tampered_receipt_payload_is_rejected` |

Local audio is deleted only against an Ed25519 purge receipt proving the archive
holds a verified copy — then only after a 24-hour grace period. **If the archive
is lost, no receipt is issued and nothing is deleted.**

### The chain format cannot drift from the backend's

The chain is built here and verified in a different repository. If the two
implementations disagree by one byte, valid chains are rejected — and nothing
about reviewing either repository alone would reveal it.

| Property | Test |
|---|---|
| The vectors are the ones the backend also holds | `test_vectors_file_is_the_agreed_one` |
| Domains match the specification | `test_domains_match_the_specification` |
| A shifted field boundary cannot collide | `test_length_prefixing_actually_separates_fields` |
| Canonical JSON is byte-exact, Bengali included | `test_canonical_json` |
| A full signed session rebuilds byte for byte | `test_agent_reproduces_the_reference_chain` |
| The backend's receipt verifies here | `test_agent_accepts_the_reference_receipt` |
| Unsupported types are refused, as on the backend | `test_canonical_json_rejects_types_the_backend_cannot_represent` |

`tests/wire_vectors.json` is checked into both repositories byte-identically and
its SHA-256 is pinned in both test suites, so editing it in one place alone
fails that repository's own tests.

### Refusing to run insecurely

| Property | Test |
|---|---|
| Wildcard origins and placeholder API keys are flagged | `test_validate_flags_wildcard_and_placeholder` |
| A plaintext backend URL is flagged | `test_production_warnings_flag_plaintext_backend` |

`Config.validate()` runs at startup. When it reports a problem — no allowed
origins, a missing pinned key, a placeholder API key — the agent starts, shows
its tray icon and **refuses to record**, reporting why. That is far easier to
diagnose than a silent failure, and much safer than filing sessions under a
guessed hospital.

### Server side

- Every `/api/v2` route requires a credential; sessions are scoped to the device
  that opened them, so one PC cannot write to another's session.
- `/segment/commit` re-reads the uploaded object from storage and recomputes its
  SHA-256. A client's claim about what it uploaded is never trusted.
- Enrolment tokens are single-use, hospital-bound and expiring, stored only as
  SHA-256. The plaintext is never persisted.
- `audit_log` is append-only, enforced by a database trigger.
- The archive worker accepts no inbound connections and holds no bucket
  credentials.

---

## Known gaps

Tracked and disclosed deliberately:

- `AIMScribe_Agent.exe` and `AIMScribeSetup.exe` are not yet Authenticode-signed.
- The CMED NER webhook secret is hardcoded and needs rotating.
- `D:\AIMSLAB_AUDIO_STORAGE` has no backup.
- The backend's `/api/v1` routes remain unauthenticated; only `/api/v2` requires
  a credential.
- mTLS between agent and backend is supported by configuration but not deployed.

---

## Handling secrets

**Both AIMScribe repositories are public.** No key, token, connection string or
password belongs in either. `.env` is gitignored; production values live in the
Render and Vercel dashboards.

Enrolment token sheets are credentials. Keep them out of version control and
delete them once the machines are installed — the database stores only the
SHA-256, so the plaintext exists nowhere else.

If a secret is committed, **rotate it**. Removing the commit is not sufficient.

---

## Patient data

Recordings and transcripts contain patient data. Do not attach them to issues,
paste them into logs, or copy them to machines outside the archive.

Agent logs redact identifiers by default (`AIMS_REDACT_LOGS=true`). Leave it on.

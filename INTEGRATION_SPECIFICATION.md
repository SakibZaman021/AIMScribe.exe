# AIMScribe ↔ CMED Integration Specification

**Version**: 1.0.0
**Date**: 2026-03-17
**Status**: Production Ready

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Part 1: Pre-Recording API (CMED → AIMScribe)](#part-1-pre-recording-api)
3. [Part 2: NER Webhook (AIMScribe → CMED)](#part-2-ner-webhook)
4. [Authentication & Security](#authentication--security)
5. [Error Handling](#error-handling)
6. [Implementation Examples](#implementation-examples)

---

## Architecture Overview

```
┌────────────────────────────────────────────────────────────────────────────┐
│                              DOCTOR'S PC                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                         CMED SYSTEM                                  │  │
│  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────┐   │  │
│  │  │ Patient     │    │ Doctor      │    │ NER Webhook Receiver    │   │  │
│  │  │ Entry Form  │───▶│ Dashboard   │◀───│ POST /api/aimscribe/ner │   │  │
│  │  └─────────────┘    └──────┬──────┘    └─────────────────────────┘   │  │
│  │                            │                       ▲                  │  │
│  └────────────────────────────┼───────────────────────┼──────────────────┘  │
│                               │                       │                     │
│                               │ POST /trigger         │ Webhook Push        │
│                               ▼                       │                     │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                    AIMSCRIBE RECORDER                                │  │
│  │                      localhost:5050                                  │  │
│  │  • Receives trigger from CMED                                        │  │
│  │  • Records audio                                                     │  │
│  │  • Uploads clips to backend                                          │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        │ Upload Clips
                                        ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                           AIMS LAB SERVER                                  │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                    AIMSCRIBE BACKEND                                 │  │
│  │                      localhost:6000                                  │  │
│  │                                                                      │  │
│  │  1. Receive clip                                                     │  │
│  │  2. Transcribe (Whisper)                                             │  │
│  │  3. Extract NER (LLM)                                                │  │
│  │  4. Store in PostgreSQL                                              │  │
│  │  5. Push to CMED webhook ─────────────────────────────────────────▶  │  │
│  │                                                                      │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## Part 1: Pre-Recording API

### CMED calls AIMScribe when doctor clicks "Patient History"

#### Endpoint

```
POST http://localhost:5050/api/v1/session/start
Content-Type: application/json
X-API-Key: {CMED_API_KEY}
```

#### Request Schema

```json
{
  "patient": {
    "id": "P12345",
    "name": "রহিম উদ্দিন",
    "age": 45,
    "gender": "Male",
    "phone": "01712345678",
    "address": "ঢাকা, বাংলাদেশ"
  },
  "doctor": {
    "id": "DR001",
    "name": "ডাঃ আহমেদ",
    "specialization": "General Medicine"
  },
  "hospital": {
    "id": "HOSP001",
    "name": "AIMS Hospital"
  },
  "health_screening": {
    "bp_systolic": 120,
    "bp_diastolic": 80,
    "pulse_rate": 72,
    "diabetes_fasting": null,
    "diabetes_random": 140,
    "height_cm": 170,
    "weight_kg": 75,
    "temperature": 98.6,
    "spo2": 98
  },
  "metadata": {
    "visit_type": "OPD",
    "visit_number": 3,
    "appointment_id": "APT789",
    "timestamp": "2026-03-17T10:30:00Z"
  },
  "callback": {
    "ner_webhook_url": "https://cmed.hospital.com/api/aimscribe/ner",
    "status_webhook_url": "https://cmed.hospital.com/api/aimscribe/status"
  }
}
```

#### Request Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `patient.id` | string | **Yes** | Unique patient ID from CMED |
| `patient.name` | string | Yes | Patient full name |
| `patient.age` | integer | Yes | Patient age in years |
| `patient.gender` | string | Yes | "Male" / "Female" / "Other" |
| `patient.phone` | string | No | Contact number |
| `patient.address` | string | No | Address |
| `doctor.id` | string | **Yes** | Doctor's unique ID |
| `doctor.name` | string | Yes | Doctor's name |
| `doctor.specialization` | string | No | Specialization |
| `hospital.id` | string | **Yes** | Hospital ID |
| `hospital.name` | string | No | Hospital name |
| `health_screening.*` | number/null | No | Health screening values |
| `metadata.visit_type` | string | No | "OPD" / "IPD" / "Emergency" |
| `metadata.appointment_id` | string | No | CMED appointment reference |
| `callback.ner_webhook_url` | string | **Yes** | URL where NER results will be pushed |
| `callback.status_webhook_url` | string | No | URL for status updates |

#### Response (200 OK)

```json
{
  "success": true,
  "data": {
    "session_id": "P12345",
    "status": "recording_started",
    "started_at": "2026-03-17T10:30:05Z",
    "previous_session_stopped": false
  },
  "message": "Recording started successfully"
}
```

#### Response (Auto-Stop Previous)

```json
{
  "success": true,
  "data": {
    "session_id": "P12346",
    "status": "recording_started",
    "started_at": "2026-03-17T10:45:00Z",
    "previous_session_stopped": true,
    "previous_session_id": "P12345"
  },
  "message": "Previous recording stopped, new recording started"
}
```

---

### Stop Recording

#### Endpoint

```
POST http://localhost:5050/api/v1/session/stop
Content-Type: application/json
X-API-Key: {CMED_API_KEY}
```

#### Request (Optional)

```json
{
  "session_id": "P12345"
}
```

#### Response

```json
{
  "success": true,
  "data": {
    "session_id": "P12345",
    "status": "stopped",
    "duration_seconds": 845,
    "clips_uploaded": 5,
    "stopped_at": "2026-03-17T10:44:05Z"
  },
  "message": "Recording stopped successfully"
}
```

---

### Get Session Status

#### Endpoint

```
GET http://localhost:5050/api/v1/session/status
X-API-Key: {CMED_API_KEY}
```

#### Response

```json
{
  "success": true,
  "data": {
    "is_recording": true,
    "session_id": "P12345",
    "patient_id": "P12345",
    "patient_name": "রহিম উদ্দিন",
    "started_at": "2026-03-17T10:30:05Z",
    "duration_seconds": 125,
    "clips_uploaded": 1,
    "clips_pending": 0
  }
}
```

---

## Part 2: NER Webhook

### AIMScribe pushes NER results to CMED after each clip is processed

#### Webhook Call (AIMScribe → CMED)

```
POST {callback.ner_webhook_url}
Content-Type: application/json
X-AIMScribe-Signature: sha256={HMAC_SIGNATURE}
X-AIMScribe-Timestamp: 1710678000
X-AIMScribe-Event: ner.extracted
```

#### Webhook Payload

```json
{
  "event": "ner.extracted",
  "timestamp": "2026-03-17T10:33:15Z",
  "session": {
    "id": "P12345",
    "patient_id": "P12345",
    "doctor_id": "DR001",
    "hospital_id": "HOSP001"
  },
  "clip": {
    "number": 1,
    "total_clips": 3,
    "duration_seconds": 180,
    "is_final": false
  },
  "ner": {
    "chief_complaints": [
      "জ্বর ৩ দিন ধরে",
      "মাথা ব্যথা",
      "শরীর ব্যথা"
    ],
    "associated_complaints": [
      "কাশি",
      "গলা ব্যথা",
      "খাবারে অরুচি"
    ],
    "history_of_presenting_illness": "৩ দিন আগে হঠাৎ জ্বর শুরু হয়েছে, সাথে মাথা ব্যথা ও শরীর ব্যথা আছে। কাশিও আছে।",
    "past_history": [
      "ডায়াবেটিস ৫ বছর ধরে",
      "উচ্চ রক্তচাপ আছে"
    ],
    "family_history": [
      "বাবার ডায়াবেটিস আছে"
    ],
    "personal_history": {
      "smoking": false,
      "alcohol": false,
      "diet": "Normal",
      "sleep": "Disturbed due to fever"
    },
    "examination_findings": [
      "Temperature: 101°F",
      "Throat congested",
      "No lymphadenopathy"
    ],
    "provisional_diagnosis": [
      "Viral fever",
      "Upper respiratory tract infection"
    ],
    "differential_diagnosis": [
      "Dengue fever",
      "Typhoid"
    ],
    "investigations_advised": [
      "CBC",
      "Dengue NS1",
      "Widal test"
    ],
    "treatment_plan": {
      "medications": [
        {
          "name": "Tab. Paracetamol",
          "generic": "Paracetamol",
          "strength": "500mg",
          "dosage": "1 tablet",
          "frequency": "3 times daily",
          "duration": "5 days",
          "instructions": "After meal"
        },
        {
          "name": "Tab. Fexofenadine",
          "generic": "Fexofenadine",
          "strength": "120mg",
          "dosage": "1 tablet",
          "frequency": "Once daily",
          "duration": "5 days",
          "instructions": "At night"
        }
      ],
      "advice": [
        "বিশ্রাম নিন",
        "পানি ও তরল খাবার বেশি খান",
        "জ্বর বাড়লে মাথায় পানি দিন"
      ]
    },
    "follow_up": {
      "duration": "7 days",
      "condition": "জ্বর না কমলে আগে আসবেন"
    },
    "referral": null
  },
  "confidence": {
    "overall": 0.92,
    "chief_complaints": 0.95,
    "diagnosis": 0.88,
    "medications": 0.94
  },
  "raw_transcript": "রোগী বলছেন যে ৩ দিন ধরে জ্বর, মাথা ব্যথা করছে..."
}
```

#### Webhook Events

| Event | Description |
|-------|-------------|
| `ner.extracted` | NER extracted from a clip (sent for each clip) |
| `ner.final` | Final consolidated NER after all clips processed |
| `session.started` | Recording session started |
| `session.stopped` | Recording session stopped |
| `session.error` | Error occurred during processing |

#### Final Consolidated NER Event

When recording stops and all clips are processed:

```json
{
  "event": "ner.final",
  "timestamp": "2026-03-17T10:45:30Z",
  "session": {
    "id": "P12345",
    "patient_id": "P12345",
    "doctor_id": "DR001",
    "hospital_id": "HOSP001",
    "duration_seconds": 845,
    "total_clips": 5
  },
  "ner": {
    // Consolidated NER from all clips (merged & deduplicated)
    // Same structure as above
  },
  "transcript": {
    "full_text": "Complete transcript of entire session...",
    "segments": [
      {
        "clip": 1,
        "start": 0,
        "end": 180,
        "text": "..."
      }
    ]
  }
}
```

---

### CMED Webhook Endpoint Requirements

CMED must implement this endpoint:

```
POST /api/aimscribe/ner
```

#### Expected Response from CMED

**Success (200 OK)**:
```json
{
  "received": true,
  "session_id": "P12345",
  "clip_number": 1
}
```

**Failure (4xx/5xx)**:
AIMScribe will retry with exponential backoff.

---

## Authentication & Security

### 1. API Key Authentication

Both systems exchange API keys during setup:

```
# CMED → AIMScribe
X-API-Key: cmed_live_abc123def456

# AIMScribe → CMED (webhook)
X-API-Key: aimscribe_live_xyz789
```

### 2. Webhook Signature Verification

AIMScribe signs all webhook payloads using HMAC-SHA256:

```
X-AIMScribe-Signature: sha256=a1b2c3d4e5f6...
X-AIMScribe-Timestamp: 1710678000
```

**CMED should verify:**

```python
import hmac
import hashlib
import time

def verify_webhook(payload: bytes, signature: str, timestamp: str, secret: str) -> bool:
    # Check timestamp (prevent replay attacks, allow 5 min window)
    current_time = int(time.time())
    request_time = int(timestamp)
    if abs(current_time - request_time) > 300:
        return False

    # Verify signature
    expected = hmac.new(
        secret.encode(),
        f"{timestamp}.{payload.decode()}".encode(),
        hashlib.sha256
    ).hexdigest()

    provided = signature.replace("sha256=", "")
    return hmac.compare_digest(expected, provided)
```

### 3. Webhook Retry Policy

If CMED webhook fails, AIMScribe retries:

| Attempt | Delay |
|---------|-------|
| 1 | Immediate |
| 2 | 5 seconds |
| 3 | 30 seconds |
| 4 | 2 minutes |
| 5 | 10 minutes |
| 6 | 1 hour |

After 6 failures, the event is logged and stored for manual retry.

---

## Error Handling

### Standard Error Response

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "patient.id is required",
    "details": {
      "field": "patient.id",
      "reason": "missing"
    }
  },
  "timestamp": "2026-03-17T10:30:00Z"
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Invalid request data |
| `AUTHENTICATION_ERROR` | 401 | Invalid or missing API key |
| `SESSION_NOT_FOUND` | 404 | Session ID not found |
| `SESSION_ALREADY_ACTIVE` | 409 | Recording already in progress |
| `RECORDER_OFFLINE` | 503 | Recorder service unavailable |
| `INTERNAL_ERROR` | 500 | Internal server error |

---

## Implementation Examples

### CMED: Starting Recording (TypeScript)

```typescript
interface StartSessionRequest {
  patient: {
    id: string;
    name: string;
    age: number;
    gender: 'Male' | 'Female' | 'Other';
  };
  doctor: {
    id: string;
    name: string;
  };
  hospital: {
    id: string;
  };
  health_screening?: HealthScreening;
  callback: {
    ner_webhook_url: string;
  };
}

async function startAIMScribeRecording(data: StartSessionRequest): Promise<void> {
  const response = await fetch('http://localhost:5050/api/v1/session/start', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': process.env.AIMSCRIBE_API_KEY
    },
    body: JSON.stringify(data)
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error.message);
  }

  const result = await response.json();
  console.log(`Recording started: ${result.data.session_id}`);
}

// Usage in CMED
await startAIMScribeRecording({
  patient: {
    id: patient.cmedId,
    name: patient.fullName,
    age: patient.age,
    gender: patient.gender
  },
  doctor: {
    id: currentDoctor.id,
    name: currentDoctor.name
  },
  hospital: {
    id: currentHospital.id
  },
  health_screening: patient.vitals,
  callback: {
    ner_webhook_url: 'https://cmed.hospital.com/api/aimscribe/ner'
  }
});
```

### CMED: Webhook Receiver (Express.js)

```typescript
import express from 'express';
import crypto from 'crypto';

const app = express();
app.use(express.json());

const WEBHOOK_SECRET = process.env.AIMSCRIBE_WEBHOOK_SECRET;

// Verify webhook signature
function verifySignature(req: express.Request): boolean {
  const signature = req.headers['x-aimscribe-signature'] as string;
  const timestamp = req.headers['x-aimscribe-timestamp'] as string;

  if (!signature || !timestamp) return false;

  // Check timestamp (5 min window)
  const now = Math.floor(Date.now() / 1000);
  if (Math.abs(now - parseInt(timestamp)) > 300) return false;

  // Verify HMAC
  const payload = JSON.stringify(req.body);
  const expected = crypto
    .createHmac('sha256', WEBHOOK_SECRET)
    .update(`${timestamp}.${payload}`)
    .digest('hex');

  const provided = signature.replace('sha256=', '');
  return crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(provided));
}

// Webhook endpoint
app.post('/api/aimscribe/ner', (req, res) => {
  // Verify signature
  if (!verifySignature(req)) {
    return res.status(401).json({ error: 'Invalid signature' });
  }

  const { event, session, clip, ner } = req.body;

  console.log(`Received ${event} for session ${session.id}`);

  switch (event) {
    case 'ner.extracted':
      // Update UI with incremental NER data
      broadcastToDoctor(session.doctor_id, {
        type: 'ner_update',
        sessionId: session.id,
        clipNumber: clip.number,
        ner: ner
      });
      break;

    case 'ner.final':
      // Save final NER to database
      saveNERToDatabase(session.patient_id, ner);

      // Notify doctor that processing is complete
      broadcastToDoctor(session.doctor_id, {
        type: 'ner_complete',
        sessionId: session.id,
        ner: ner
      });
      break;

    case 'session.error':
      // Handle error
      notifyError(session.doctor_id, req.body.error);
      break;
  }

  res.json({
    received: true,
    session_id: session.id,
    clip_number: clip?.number
  });
});

app.listen(3000);
```

---

## Configuration Exchange

Before going live, both teams exchange:

| From | To | Item |
|------|----|------|
| CMED | AIMScribe | API Key for authentication |
| CMED | AIMScribe | Webhook URLs (production & staging) |
| AIMScribe | CMED | API Key for authentication |
| AIMScribe | CMED | Webhook secret for signature verification |

---

## Testing Checklist

### CMED Team
- [ ] Can call `/api/v1/session/start` successfully
- [ ] Can call `/api/v1/session/stop` successfully
- [ ] Webhook endpoint receives NER data
- [ ] Webhook signature verification works
- [ ] UI updates when NER data arrives
- [ ] Error handling for recorder offline

### AIMScribe Team
- [ ] Receives session start requests
- [ ] Saves patient data to database
- [ ] Recording starts correctly
- [ ] Clips uploaded and processed
- [ ] NER webhook calls succeed
- [ ] Retry logic works for failed webhooks

---

## Support & Contact

**AIMScribe Team**: aims.lab@example.com
**CMED Team**: cmed.support@example.com

---

*Document Version: 1.0.0 | Last Updated: 2026-03-17*

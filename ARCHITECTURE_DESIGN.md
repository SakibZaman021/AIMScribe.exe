# AIMScribe Industrial Architecture Design

## Version: 2.0 - Distributed System with WebSocket Communication

---

## 1. System Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              CLOUD LAYER                                        │
│                                                                                 │
│  ┌──────────────────┐         ┌──────────────────────────────────────────────┐  │
│  │   CMED System    │         │           AIMS LAB BACKEND                   │  │
│  │   (Vercel)       │         │                                              │  │
│  │                  │         │  ┌────────────┐  ┌────────────┐  ┌────────┐  │  │
│  │  - Doctor Login  │◄───────▶│  │  FastAPI   │  │  Worker    │  │ Redis  │  │  │
│  │  - Patient Mgmt  │   API   │  │  Gateway   │  │  (Whisper  │  │ Queue  │  │  │
│  │  - Dashboard     │         │  │            │  │   + NER)   │  │        │  │  │
│  │                  │         │  └────────────┘  └────────────┘  └────────┘  │  │
│  └──────────────────┘         │                                              │  │
│                               │  ┌────────────┐  ┌────────────┐  ┌────────┐  │  │
│                               │  │ PostgreSQL │  │   MinIO    │  │   R2   │  │  │
│                               │  │ (metadata) │  │  (chunks)  │  │(final) │  │  │
│                               │  └────────────┘  └────────────┘  └────────┘  │  │
│                               └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                           ▲
                                           │ HTTPS (Chunk Upload)
                                           │
┌──────────────────────────────────────────┼──────────────────────────────────────┐
│                                          │                                      │
│    HOSPITAL A            HOSPITAL B      │         HOSPITAL C                   │
│                                          │                                      │
│  ┌──────────────┐      ┌──────────────┐  │      ┌──────────────┐                │
│  │ Doctor PC 1  │      │ Doctor PC 5  │  │      │ Doctor PC 12 │                │
│  │              │      │              │  │      │              │                │
│  │ ┌──────────┐ │      │ ┌──────────┐ │  │      │ ┌──────────┐ │                │
│  │ │ Browser  │ │      │ │ Browser  │ │  │      │ │ Browser  │ │                │
│  │ │ (CMED)   │ │      │ │ (CMED)   │ │  │      │ │ (CMED)   │ │                │
│  │ │ Dr.Shuvo │ │      │ │ Dr.Rahim │ │  │      │ │ Dr.Shuvo │ │                │
│  │ └────┬─────┘ │      │ └────┬─────┘ │  │      │ └────┬─────┘ │                │
│  │      │WS     │      │      │WS     │  │      │      │WS     │                │
│  │      ▼       │      │      ▼       │  │      │      ▼       │                │
│  │ ┌──────────┐ │      │ ┌──────────┐ │  │      │ ┌──────────┐ │                │
│  │ │AIMScribe │ │      │ │AIMScribe │ │  │      │ │AIMScribe │ │                │
│  │ │   .exe   │─┼──────┼─┼───.exe───│─┼──┴──────┼─┼───.exe───│─┼────────────────│
│  │ └──────────┘ │      │ └──────────┘ │         │ └──────────┘ │                │
│  └──────────────┘      └──────────────┘         └──────────────┘                │
│                                                                                 │
│                            DOCTOR PCs (20+)                                     │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Communication Flow

### 2.1 Browser ↔ Local AIMScribe (WebSocket)

The browser (CMED) runs on the SAME PC as AIMScribe.exe. This enables direct WebSocket communication.

```javascript
// CMED Frontend (Browser)
const localRecorder = new WebSocket('ws://localhost:5050/ws');

localRecorder.onopen = () => {
    console.log('Connected to local AIMScribe');
};

// When doctor clicks "Patient History"
function startRecording(patientId) {
    localRecorder.send(JSON.stringify({
        command: 'start',
        doctor_id: currentDoctor.id,      // From CMED login
        doctor_name: currentDoctor.name,
        hospital_id: currentHospital.id,  // From CMED context
        hospital_name: currentHospital.name,
        patient_id: patientId,
        patient_name: patientData.name,
        health_screening: patientData.vitals
    }));
}
```

### 2.2 Why This Works

| Scenario | Dr. Shuvo at Hospital A | Dr. Shuvo at Hospital C |
|----------|------------------------|------------------------|
| Browser | CMED logged in as DR1245 | CMED logged in as DR1245 |
| Local App | AIMScribe.exe on PC | AIMScribe.exe on PC |
| Connection | ws://localhost:5050 | ws://localhost:5050 |
| Result | Recording starts with DR1245 | Recording starts with DR1245 |

**The doctor_id travels WITH the doctor via CMED login!**

---

## 3. AIMScribe.exe Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AIMScribe.exe                                       │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    WebSocket Server (Port 5050)                     │    │
│  │                                                                     │    │
│  │  - Accepts connections from localhost only (security)              │    │
│  │  - Receives commands: start, stop, status                          │    │
│  │  - Sends events: recording_started, clip_uploaded, ner_ready       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    Recording Controller                             │    │
│  │                                                                     │    │
│  │  - Manages audio recording state                                   │    │
│  │  - Handles start/stop commands                                     │    │
│  │  - Auto-stop previous session if new patient                       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    Audio Pipeline                                   │    │
│  │                                                                     │    │
│  │  ┌────────────┐   ┌────────────┐   ┌────────────┐   ┌────────────┐  │    │
│  │  │ PyAudio    │──▶│ Silence    │──▶│ Chunk      │──▶│ Async      │  │    │
│  │  │ Capture    │   │ Detection  │   │ Splitter   │   │ Uploader   │  │    │
│  │  │            │   │            │   │ (3 min)    │   │            │  │    │
│  │  └────────────┘   └────────────┘   └────────────┘   └────────────┘  │    │
│  │                                                                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                        │
│                                    │ HTTPS Upload                           │
│                                    ▼                                        │
│                         AIMS LAB Backend                                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Message Protocol

### 4.1 CMED → AIMScribe (Commands)

```json
// Start Recording
{
    "command": "start",
    "timestamp": "2026-04-15T10:30:00Z",
    "session": {
        "doctor_id": "DR1245",
        "doctor_name": "Dr. Shuvo",
        "hospital_id": "HOSP_AALO",
        "hospital_name": "Aalo Clinic Karail",
        "patient_id": "P5678",
        "patient_name": "রহিম উদ্দিন",
        "age": "45",
        "gender": "Male"
    },
    "health_screening": {
        "bp_systolic": "120",
        "bp_diastolic": "80",
        "pulse_rate": "72"
    },
    "callback": {
        "ner_webhook_url": "https://cmed.vercel.app/api/webhook/ner"
    }
}

// Stop Recording
{
    "command": "stop",
    "timestamp": "2026-04-15T10:45:00Z"
}

// Get Status
{
    "command": "status"
}
```

### 4.2 AIMScribe → CMED (Events)

```json
// Recording Started
{
    "event": "recording_started",
    "timestamp": "2026-04-15T10:30:01Z",
    "session_id": "P5678",
    "patient_id": "P5678"
}

// Clip Uploaded
{
    "event": "clip_uploaded",
    "timestamp": "2026-04-15T10:33:05Z",
    "session_id": "P5678",
    "clip_number": 1,
    "duration_seconds": 180
}

// Clip Uploaded (real-time progress)
{
    "event": "clip_uploaded",
    "timestamp": "2026-04-15T10:33:05Z",
    "session_id": "P5678",
    "patient_id": "P5678",
    "clip_number": 1,
    "duration_seconds": 180,
    "message": "Clip uploaded successfully"
}

// NER Ready (from backend via webhook, relayed to browser)
{
    "event": "ner_ready",
    "timestamp": "2026-04-15T10:33:45Z",
    "session_id": "P5678",
    "patient_id": "P5678",
    "version": 1,
    "ner": {
        "chief_complaints": ["জ্বর", "মাথা ব্যথা"],
        "diagnosis": ["Viral fever"]
    },
    "transcript_preview": "রোগী বলছেন জ্বর আর মাথা ব্যথা..."
}

// Recording Stopped
{
    "event": "recording_stopped",
    "timestamp": "2026-04-15T10:45:02Z",
    "session_id": "P5678",
    "total_duration_seconds": 900,
    "total_clips": 5
}

// Status Response
{
    "event": "status",
    "is_recording": true,
    "session_id": "P5678",
    "patient_id": "P5678",
    "doctor_id": "DR1245",
    "duration_seconds": 125
}
```

---

## 5. Security Considerations

### 5.1 Local-Only WebSocket

```python
# AIMScribe WebSocket server - Accept only localhost
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Verify connection is from localhost
    client_host = websocket.client.host
    if client_host not in ['127.0.0.1', 'localhost', '::1']:
        await websocket.close(code=4003, reason="Only localhost allowed")
        return

    await websocket.accept()
    # ... handle messages
```

### 5.2 CORS for HTTP Fallback

```python
# Allow Vercel domain for HTTP requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://cmed.vercel.app",
        "https://*.vercel.app",
        "http://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 6. Handling HTTPS → ws://localhost

Modern browsers have special handling for localhost:

| Browser | HTTPS → ws://localhost | Status |
|---------|------------------------|--------|
| Chrome | Allowed | ✅ Works |
| Firefox | Allowed | ✅ Works |
| Edge | Allowed | ✅ Works |
| Safari | May require flag | ⚠️ Test |

### 6.1 Fallback: Secure WebSocket with Self-Signed Cert

If needed, AIMScribe can generate a self-signed certificate for wss://localhost:5050

```python
# Generate self-signed cert on first run
import ssl
ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ssl_context.load_cert_chain('localhost.pem', 'localhost-key.pem')
```

---

## 7. Scaling Considerations

### 7.1 Current Scale
- 7-10 hospitals
- 20 doctors
- 20 AIMScribe.exe instances

### 7.2 Backend Scaling

```
                    Load Balancer
                         │
          ┌──────────────┼──────────────┐
          │              │              │
          ▼              ▼              ▼
    ┌──────────┐   ┌──────────┐   ┌──────────┐
    │ API Pod 1│   │ API Pod 2│   │ API Pod 3│
    └──────────┘   └──────────┘   └──────────┘
          │              │              │
          └──────────────┼──────────────┘
                         │
                    ┌────┴────┐
                    │  Redis  │ (Job Queue)
                    └────┬────┘
                         │
          ┌──────────────┼──────────────┐
          │              │              │
          ▼              ▼              ▼
    ┌──────────┐   ┌──────────┐   ┌──────────┐
    │Worker Pod│   │Worker Pod│   │Worker Pod│
    │(Whisper) │   │(Whisper) │   │(Whisper) │
    └──────────┘   └──────────┘   └──────────┘
```

### 7.3 Storage Scaling

| Stage | Storage | Retention |
|-------|---------|-----------|
| Upload | MinIO (local) | 24 hours |
| Processing | PostgreSQL | Permanent |
| Archive | Cloudflare R2 | 7 years |

---

## 8. Data Flow Summary

```
1. Doctor logs into CMED (browser) → Gets doctor_id, hospital_id
2. Doctor opens Patient P5678 → Gets patient_id, health_screening
3. Doctor clicks "Patient History"
4. CMED (browser) sends WebSocket command to localhost:5050
5. AIMScribe.exe receives command with all context
6. AIMScribe starts recording
7. Every 3 minutes:
   a. Chunk saved locally
   b. Uploaded to AIMS LAB Backend (MinIO)
   c. Backend queues transcription job
   d. Worker transcribes (GPT-4o)
   e. Worker extracts NER (GPT-5.2)
   f. NER saved to PostgreSQL
   g. Webhook sent to CMED
   h. CMED updates UI via WebSocket to browser
8. Doctor clicks "Stop"
9. AIMScribe stops recording
10. Full recording uploaded to Cloudflare R2
11. Session marked complete
```

---

## 9. Deployment

### 9.1 AIMScribe.exe Distribution

```
Distribution Package:
├── AIMScribe_Recorder.exe       # Main executable
├── install_autostart.bat        # Add to Windows Startup
├── uninstall_autostart.bat      # Remove from Startup
└── README.txt                   # Instructions
```

### 9.2 Installation Steps (Per Doctor PC)

1. Download AIMScribe package
2. Extract to any folder
3. Run `install_autostart.bat`
4. Restart PC (or run exe manually)
5. Green icon appears in system tray
6. Done - no login required

### 9.3 CMED Configuration

```javascript
// CMED needs to know recorder URL (always localhost for direct connection)
const RECORDER_WS_URL = 'ws://localhost:5050/ws';
const RECORDER_HTTP_URL = 'http://localhost:5050';
```

---

## 10. Monitoring & Troubleshooting

### 10.1 Health Check

CMED can check if AIMScribe is running:

```javascript
async function checkRecorderHealth() {
    try {
        const response = await fetch('http://localhost:5050/health');
        return response.ok;
    } catch {
        return false; // Not running
    }
}
```

### 10.2 Connection Status UI

```
┌─────────────────────────────────────┐
│  CMED Dashboard                     │
│                                     │
│  AIMScribe Status: 🟢 Connected     │
│  [Patient History]                  │
│                                     │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│  CMED Dashboard                     │
│                                     │
│  AIMScribe Status: 🔴 Not Running   │
│  Please start AIMScribe Recorder    │
│  [Download] [Troubleshoot]          │
│                                     │
└─────────────────────────────────────┘
```

---

*Document Version: 2.0 | Architecture: Distributed WebSocket | Date: 2026-04-15*

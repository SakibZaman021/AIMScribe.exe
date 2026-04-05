# AIMScribe System v1.0

Split architecture with System Tray Recorder + CMED Web Frontend + AIMS LAB Server.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    DOCTOR'S PC                                  │
│  ┌─────────────────┐       ┌─────────────────────────────────┐  │
│  │   CMED Web      │       │   AIMScribe Recorder            │  │
│  │   (NextJS)      │──────▶│   (System Tray)                 │  │
│  │   :3000         │       │   :5050                         │  │
│  └────────┬────────┘       └──────────────┬──────────────────┘  │
│           │                               │                     │
└───────────┼───────────────────────────────┼─────────────────────┘
            │                               │
            │ Poll NER                      │ Upload Clips
            │                               │
┌───────────┼───────────────────────────────┼─────────────────────┐
│           ▼                               ▼                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              AIMScribe Backend (Docker)                 │    │
│  │   API :6000  │  PostgreSQL  │  Redis  │  MinIO          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              AIMS LAB Server                            │    │
│  │   :7000  │  Audio Storage: D:\AIMSLAB_AUDIO_STORAGE     │    │
│  └─────────────────────────────────────────────────────────┘    │
│                        AIMS LAB SERVER                          │
└─────────────────────────────────────────────────────────────────┘
```

## Components

| Component | Port | Description |
|-----------|------|-------------|
| CMED Web | 3000 | Doctor dashboard (NextJS + Tailwind) |
| Recorder | 5050 | System tray app, receives triggers |
| Backend API | 6000 | FastAPI, handles transcription/NER |
| AIMS LAB Server | 7000 | Receives and stores audio files |

## Key Features

### 1. Session ID = Patient ID
- No confusing auto-generated session IDs
- `patient_id` from CMED is used as the unique identifier
- Easy to search and track patients

### 2. Auto Start/Stop
- Clicking "Patient History" for a new patient automatically:
  - Stops any current recording
  - Starts new recording for the new patient

### 3. Force Reset for Crash Recovery
- If CMED crashes, run `force-reset.bat`
- Or call `POST http://localhost:5050/force-reset`
- Clears stuck recording state

### 4. Audio File Forwarding
- Recordings are forwarded to AIMS LAB server
- Doctor's PC doesn't accumulate large audio files
- All audio stored centrally at `D:\AIMSLAB_AUDIO_STORAGE`

### 5. Health Screening Data
- Health screening data is sent with session creation
- Stored in AIMScribe PostgreSQL database

## Quick Start

### Option 1: Start Everything
```batch
start-all.bat
```

### Option 2: Start Components Individually
```batch
# Terminal 1: Start Backend (Docker)
start-backend.bat

# Terminal 2: Start AIMS LAB Server
start-aimslab-server.bat

# Terminal 3: Start Recorder
start-recorder.bat

# Terminal 4: Start CMED Web
start-cmed.bat
```

### Check System Status
```batch
check-status.bat
```

### Force Reset (Crash Recovery)
```batch
force-reset.bat
```

### Stop Everything
```batch
stop-all.bat
```

## User Flow

1. **Reception** fills in patient info at `http://localhost:3000`
   - Patient ID, Name, Age, Gender
   - Health Screening (BP, pulse, diabetes, height, weight, temperature)

2. **Doctor** clicks "Go to Doctor Dashboard"

3. **Doctor** clicks "Patient History" tab
   - Recording starts automatically
   - Red indicator shows recording in progress

4. **Doctor** conducts consultation (audio recorded)

5. **System** automatically:
   - Splits recording into 3-minute clips
   - Uploads clips to Backend (MinIO)
   - Backend transcribes and extracts NER
   - NER appears in prescription fields

6. **Doctor** clicks "Stop Recording"
   - Recording finishes
   - Full recording forwarded to AIMS LAB server
   - Local copy deleted to save space

7. **Doctor** reviews/edits prescription and saves

## API Endpoints

### Recorder (localhost:5050)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /health | Health check |
| GET | /status | Current recording status |
| POST | /trigger | Start recording (with patient context) |
| POST | /stop | Stop current recording |
| POST | /force-reset | Force reset state (crash recovery) |

### AIMS LAB Server (localhost:7000)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /health | Health check |
| POST | /receive-recording | Receive full recording file |
| POST | /receive-clip | Receive clip file |
| POST | /create-session | Create session in backend |
| GET | /patients | List all patients with recordings |
| GET | /patient/{id}/recordings | Get patient's recordings |

## File Structure

```
aimscribe.exe.v1/
├── start-all.bat              # Start everything
├── start-backend.bat          # Start Docker services
├── start-recorder.bat         # Start recorder
├── start-cmed.bat             # Start CMED web
├── start-aimslab-server.bat   # Start AIMS LAB server
├── stop-all.bat               # Stop everything
├── force-reset.bat            # Force reset recorder
├── check-status.bat           # Check system status
├── README.md
│
├── recorder/                  # System tray recorder
│   ├── main.py
│   ├── config.py
│   ├── requirements.txt
│   ├── api/
│   │   └── trigger_server.py
│   └── core/
│       ├── recorder.py
│       ├── simple_splitter.py
│       ├── clip_uploader.py
│       ├── session_controller.py
│       └── file_forwarder.py
│
├── cmed-web/                  # Doctor dashboard
│   ├── package.json
│   ├── next.config.js
│   └── src/app/
│       ├── page.tsx          # Patient entry
│       └── dashboard/
│           └── page.tsx      # Doctor dashboard
│
└── aimslab-server/            # Audio file receiver
    ├── main.py
    ├── config.py
    └── requirements.txt
```

## Requirements

- **Python 3.11+** (for Recorder and AIMS LAB Server)
- **Node.js 18+** (for CMED Web)
- **Docker Desktop** (for Backend)

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| AIMSCRIBE_BACKEND_URL | http://localhost:6000 | Backend API URL |
| AIMSLAB_SERVER_URL | http://localhost:7000 | AIMS LAB server URL |
| TRIGGER_PORT | 5050 | Recorder trigger port |

### AIMS LAB Server Storage

Audio files are stored at:
```
D:\AIMSLAB_AUDIO_STORAGE\
├── recordings\
│   └── {patient_id}\
│       └── {patient_id}_{timestamp}.wav
└── clips\
    └── {patient_id}\
        └── {patient_id}_clip{N}_{timestamp}.wav
```

## Troubleshooting

### Recording won't start
1. Check if recorder is running: `check-status.bat`
2. Try force reset: `force-reset.bat`
3. Check logs: `recorder\logs\`

### CMED crashed, can't stop recording
1. Run `force-reset.bat`
2. This clears the stuck state
3. Now you can start a new recording

### Audio not forwarded to AIMS LAB
1. Check AIMS LAB server is running
2. Check network connectivity
3. Local copy is kept if forward fails

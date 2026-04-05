"""
AIMS LAB Local Server
Receives audio files from doctor PCs and stores them locally.
Also forwards session data to AIMScribe backend database.
"""
import logging
import shutil
import aiohttp
import uvicorn
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import server_config, storage_config, db_config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Pydantic models
class SessionData(BaseModel):
    """Session data from recorder"""
    patient_id: str
    patient_name: str = ""
    age: str = ""
    gender: str = ""
    doctor_id: str = ""
    hospital_id: str = ""
    health_screening: Dict[str, Any] = {}
    recording_date: str = ""
    start_time: str = ""
    end_time: str = ""


class FileReceiveResponse(BaseModel):
    """Response after receiving a file"""
    status: str
    patient_id: str
    file_path: str
    message: str


class SessionCreateResponse(BaseModel):
    """Response after creating session in backend"""
    status: str
    patient_id: str
    backend_session_id: Optional[str] = None
    message: str


# Create FastAPI app
app = FastAPI(
    title="AIMS LAB Audio Server",
    description="Receives and stores audio files from doctor PCs",
    version="1.0.0"
)

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "aimslab-audio-server",
        "storage_dir": str(storage_config.audio_storage_dir),
        "timestamp": datetime.now().isoformat()
    }


@app.post("/receive-recording", response_model=FileReceiveResponse)
async def receive_recording(
    file: UploadFile = File(...),
    patient_id: str = Form(...),
    patient_name: str = Form(""),
    recording_date: str = Form(""),
):
    """
    Receive a full recording file from a doctor PC.
    Stores it in the AIMS LAB local storage.
    """
    try:
        # Create patient directory
        patient_dir = storage_config.recordings_dir / patient_id
        patient_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{patient_id}_{timestamp}.wav"
        file_path = patient_dir / filename

        # Save file
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        file_size_mb = file_path.stat().st_size / (1024 * 1024)

        logger.info(f"Received recording for patient {patient_id}: {filename} ({file_size_mb:.2f} MB)")

        return FileReceiveResponse(
            status="success",
            patient_id=patient_id,
            file_path=str(file_path),
            message=f"Recording saved: {filename} ({file_size_mb:.2f} MB)"
        )

    except Exception as e:
        logger.error(f"Error receiving recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/receive-clip", response_model=FileReceiveResponse)
async def receive_clip(
    file: UploadFile = File(...),
    patient_id: str = Form(...),
    clip_index: int = Form(...),
):
    """
    Receive a clip file from a doctor PC.
    Stores it in the AIMS LAB local storage.
    """
    try:
        # Create patient clips directory
        patient_dir = storage_config.clips_dir / patient_id
        patient_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{patient_id}_clip{clip_index:03d}_{timestamp}.wav"
        file_path = patient_dir / filename

        # Save file
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        file_size_kb = file_path.stat().st_size / 1024

        logger.info(f"Received clip {clip_index} for patient {patient_id}: {filename} ({file_size_kb:.2f} KB)")

        return FileReceiveResponse(
            status="success",
            patient_id=patient_id,
            file_path=str(file_path),
            message=f"Clip saved: {filename}"
        )

    except Exception as e:
        logger.error(f"Error receiving clip: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/create-session", response_model=SessionCreateResponse)
async def create_session_in_backend(session_data: SessionData):
    """
    Create a session in the AIMScribe backend database.
    This forwards the session data including health screening to the backend.
    """
    try:
        # Prepare payload for backend
        payload = {
            "patient_id": session_data.patient_id,
            "patient_name": session_data.patient_name,
            "age": session_data.age,
            "gender": session_data.gender,
            "doctor_id": session_data.doctor_id,
            "hospital_id": session_data.hospital_id,
            "health_screening": session_data.health_screening,
            "recording_date": session_data.recording_date or datetime.now().strftime("%Y-%m-%d"),
            "start_time": session_data.start_time or datetime.now().strftime("%H:%M:%S"),
        }

        logger.info(f"Creating session in backend for patient: {session_data.patient_id}")

        async with aiohttp.ClientSession() as http_session:
            async with http_session.post(
                f"{db_config.backend_url}/api/v1/session/create",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    backend_session_id = result.get("session_id")

                    logger.info(f"Backend session created: {backend_session_id}")

                    return SessionCreateResponse(
                        status="success",
                        patient_id=session_data.patient_id,
                        backend_session_id=backend_session_id,
                        message="Session created in backend"
                    )
                else:
                    error_text = await response.text()
                    logger.error(f"Backend error: {response.status} - {error_text}")
                    raise HTTPException(
                        status_code=response.status,
                        detail=f"Backend error: {error_text}"
                    )

    except aiohttp.ClientError as e:
        logger.error(f"Connection error to backend: {e}")
        raise HTTPException(status_code=503, detail=f"Cannot connect to backend: {e}")
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/patients")
async def list_patients():
    """List all patients with stored recordings"""
    try:
        patients = []

        # Check recordings directory
        if storage_config.recordings_dir.exists():
            for patient_dir in storage_config.recordings_dir.iterdir():
                if patient_dir.is_dir():
                    recordings = list(patient_dir.glob("*.wav"))
                    patients.append({
                        "patient_id": patient_dir.name,
                        "recording_count": len(recordings),
                        "total_size_mb": sum(f.stat().st_size for f in recordings) / (1024 * 1024)
                    })

        return {
            "status": "success",
            "patient_count": len(patients),
            "patients": patients
        }

    except Exception as e:
        logger.error(f"Error listing patients: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/patient/{patient_id}/recordings")
async def get_patient_recordings(patient_id: str):
    """Get all recordings for a specific patient"""
    try:
        patient_dir = storage_config.recordings_dir / patient_id

        if not patient_dir.exists():
            return {
                "status": "success",
                "patient_id": patient_id,
                "recordings": []
            }

        recordings = []
        for file_path in patient_dir.glob("*.wav"):
            stat = file_path.stat()
            recordings.append({
                "filename": file_path.name,
                "size_mb": stat.st_size / (1024 * 1024),
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat()
            })

        return {
            "status": "success",
            "patient_id": patient_id,
            "recording_count": len(recordings),
            "recordings": recordings
        }

    except Exception as e:
        logger.error(f"Error getting patient recordings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def main():
    """Main entry point"""
    print("=" * 60)
    print("AIMS LAB Audio Server")
    print("=" * 60)
    print(f"Storage Directory: {storage_config.audio_storage_dir}")
    print(f"Backend URL: {db_config.backend_url}")
    print(f"Server: http://{server_config.host}:{server_config.port}")
    print("=" * 60)

    uvicorn.run(
        app,
        host=server_config.host,
        port=server_config.port,
        log_level="info"
    )


if __name__ == "__main__":
    main()

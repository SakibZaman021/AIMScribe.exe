"""
AIMScribe Recorder API Server
Industrial-grade API for CMED integration.

Endpoints:
- POST /api/v1/session/start - Start recording with patient context
- POST /api/v1/session/stop - Stop current recording
- GET /api/v1/session/status - Get recording status
- POST /api/v1/session/force-reset - Force reset (crash recovery)
- GET /health - Health check
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.session_controller import SessionController, SessionContext

logger = logging.getLogger(__name__)


# ============================================================
# Request/Response Models
# ============================================================

class PatientInfo(BaseModel):
    """Patient information from CMED"""
    id: str = Field(..., description="Unique patient ID from CMED")
    name: str = Field("", description="Patient full name")
    age: int = Field(0, description="Patient age in years")
    gender: str = Field("", description="Male/Female/Other")
    phone: str = Field("", description="Contact number")
    address: str = Field("", description="Address")


class DoctorInfo(BaseModel):
    """Doctor information"""
    id: str = Field("DR_DEFAULT", description="Doctor's unique ID")
    name: str = Field("", description="Doctor's name")
    specialization: str = Field("", description="Specialization")


class HospitalInfo(BaseModel):
    """Hospital information"""
    id: str = Field("HOSP_DEFAULT", description="Hospital ID")
    name: str = Field("", description="Hospital name")


class HealthScreening(BaseModel):
    """Health screening data"""
    bp_systolic: Optional[float] = None
    bp_diastolic: Optional[float] = None
    pulse_rate: Optional[float] = None
    diabetes_fasting: Optional[float] = None
    diabetes_random: Optional[float] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    temperature: Optional[float] = None
    spo2: Optional[float] = None


class SessionMetadata(BaseModel):
    """Session metadata"""
    visit_type: str = Field("OPD", description="OPD/IPD/Emergency")
    visit_number: int = Field(1, description="Visit number")
    appointment_id: str = Field("", description="CMED appointment reference")
    timestamp: str = Field("", description="ISO timestamp")


class CallbackConfig(BaseModel):
    """Webhook callback configuration"""
    ner_webhook_url: str = Field(..., description="URL where NER results will be pushed")
    status_webhook_url: str = Field("", description="URL for status updates")


class StartSessionRequest(BaseModel):
    """Request to start a recording session"""
    patient: PatientInfo
    doctor: DoctorInfo = Field(default_factory=DoctorInfo)
    hospital: HospitalInfo = Field(default_factory=HospitalInfo)
    health_screening: HealthScreening = Field(default_factory=HealthScreening)
    metadata: SessionMetadata = Field(default_factory=SessionMetadata)
    callback: CallbackConfig


class StopSessionRequest(BaseModel):
    """Request to stop a recording session"""
    session_id: Optional[str] = None


class SessionData(BaseModel):
    """Session data in response"""
    session_id: str
    status: str
    started_at: Optional[str] = None
    stopped_at: Optional[str] = None
    duration_seconds: float = 0
    clips_uploaded: int = 0
    previous_session_stopped: bool = False
    previous_session_id: Optional[str] = None


class StatusData(BaseModel):
    """Status data"""
    is_recording: bool
    session_id: Optional[str]
    patient_id: Optional[str]
    patient_name: Optional[str]
    started_at: Optional[str]
    duration_seconds: float
    clips_uploaded: int = 0
    clips_pending: int = 0


class SuccessResponse(BaseModel):
    """Standard success response"""
    success: bool = True
    data: Any
    message: str


class ErrorDetail(BaseModel):
    """Error detail"""
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Standard error response"""
    success: bool = False
    error: ErrorDetail
    timestamp: str


# ============================================================
# FastAPI Application
# ============================================================

app = FastAPI(
    title="AIMScribe Recorder API",
    description="Recording API for CMED integration",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Global State
# ============================================================

_controller: Optional[SessionController] = None
_api_keys: set = {"cmed_live_default", "cmed_test_key"}  # Configure in production


def init_controller(
    backend_url: str = "http://localhost:6000",
    aimslab_server_url: str = "http://localhost:7000"
):
    """Initialize the session controller"""
    global _controller
    _controller = SessionController(
        backend_url=backend_url,
        aimslab_server_url=aimslab_server_url
    )
    logger.info("Session controller initialized")
    logger.info(f"  Backend URL: {backend_url}")
    logger.info(f"  AIMS LAB Server: {aimslab_server_url}")


# ============================================================
# Error Handlers
# ============================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": "HTTP_ERROR",
                "message": exc.detail,
                "details": None
            },
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An internal error occurred",
                "details": {"exception": str(exc)}
            },
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    )


# ============================================================
# Authentication (Optional - can be enabled in production)
# ============================================================

def verify_api_key(x_api_key: Optional[str] = Header(None)) -> bool:
    """Verify API key (disabled by default for local development)"""
    # In production, uncomment:
    # if not x_api_key or x_api_key not in _api_keys:
    #     raise HTTPException(status_code=401, detail="Invalid API key")
    return True


# ============================================================
# Health Check
# ============================================================

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "aimscribe-recorder",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


# ============================================================
# Session Endpoints
# ============================================================

@app.post("/api/v1/session/start", response_model=SuccessResponse)
async def start_session(
    request: StartSessionRequest,
    x_api_key: Optional[str] = Header(None)
):
    """
    Start a recording session.

    Called when doctor clicks "Patient History" in CMED.
    If already recording, automatically stops previous session.
    """
    verify_api_key(x_api_key)

    if _controller is None:
        raise HTTPException(status_code=503, detail="Controller not initialized")

    logger.info(f"Start session request for patient: {request.patient.id}")
    logger.info(f"Webhook URL: {request.callback.ner_webhook_url}")

    try:
        # Convert health screening to dict with string values (backend requirement)
        health_screening = {}
        hs = request.health_screening
        if hs.bp_systolic is not None:
            health_screening["bp_systolic"] = str(hs.bp_systolic)
        if hs.bp_diastolic is not None:
            health_screening["bp_diastolic"] = str(hs.bp_diastolic)
        if hs.pulse_rate is not None:
            health_screening["pulse_rate"] = str(hs.pulse_rate)
        if hs.diabetes_fasting is not None:
            health_screening["diabetes_fasting"] = str(hs.diabetes_fasting)
        if hs.diabetes_random is not None:
            health_screening["diabetes_random"] = str(hs.diabetes_random)
        if hs.height_cm is not None:
            health_screening["height_cm"] = str(hs.height_cm)
        if hs.weight_kg is not None:
            health_screening["weight_kg"] = str(hs.weight_kg)
        if hs.temperature is not None:
            health_screening["temperature"] = str(hs.temperature)
        if hs.spo2 is not None:
            health_screening["spo2"] = str(hs.spo2)

        # Create session context
        context = SessionContext(
            patient_id=request.patient.id,
            patient_name=request.patient.name,
            age=str(request.patient.age),
            gender=request.patient.gender,
            doctor_id=request.doctor.id,
            hospital_id=request.hospital.id,
            health_screening=health_screening,
            ner_webhook_url=request.callback.ner_webhook_url,
            status_webhook_url=request.callback.status_webhook_url
        )

        # Handle trigger
        result = await _controller.handle_trigger(context)

        return SuccessResponse(
            success=True,
            data=SessionData(
                session_id=result.get("session_id", request.patient.id),
                status=result.get("status", "recording_started"),
                started_at=datetime.utcnow().isoformat() + "Z",
                previous_session_stopped=result.get("previous_session_stopped", False),
                previous_session_id=result.get("previous_session_id")
            ),
            message="Recording started successfully"
        )

    except Exception as e:
        logger.error(f"Start session error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/session/stop", response_model=SuccessResponse)
async def stop_session(
    request: StopSessionRequest = None,
    x_api_key: Optional[str] = Header(None)
):
    """
    Stop the current recording session.

    Called when doctor clicks "Stop Recording" in CMED.
    """
    verify_api_key(x_api_key)

    if _controller is None:
        raise HTTPException(status_code=503, detail="Controller not initialized")

    logger.info("Stop session request received")

    try:
        result = await _controller.handle_stop()

        if result.get("status") == "not_recording":
            return SuccessResponse(
                success=True,
                data=SessionData(
                    session_id="",
                    status="not_recording"
                ),
                message="No active recording to stop"
            )

        return SuccessResponse(
            success=True,
            data=SessionData(
                session_id=result.get("session_id", ""),
                status="stopped",
                stopped_at=datetime.utcnow().isoformat() + "Z",
                duration_seconds=result.get("duration_seconds", 0),
                clips_uploaded=result.get("clips_uploaded", 0)
            ),
            message="Recording stopped successfully"
        )

    except Exception as e:
        logger.error(f"Stop session error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/session/status", response_model=SuccessResponse)
async def get_session_status(x_api_key: Optional[str] = Header(None)):
    """
    Get current recording session status.
    """
    verify_api_key(x_api_key)

    if _controller is None:
        return SuccessResponse(
            success=True,
            data=StatusData(
                is_recording=False,
                session_id=None,
                patient_id=None,
                patient_name=None,
                started_at=None,
                duration_seconds=0
            ),
            message="Controller not initialized"
        )

    status = _controller.get_status()

    return SuccessResponse(
        success=True,
        data=StatusData(
            is_recording=status.get("is_recording", False),
            session_id=status.get("session_id"),
            patient_id=status.get("patient_id"),
            patient_name=status.get("patient_name"),
            started_at=status.get("start_time"),
            duration_seconds=status.get("duration_seconds", 0),
            clips_uploaded=status.get("clips_uploaded", 0),
            clips_pending=status.get("clips_pending", 0)
        ),
        message="Status retrieved successfully"
    )


@app.post("/api/v1/session/force-reset", response_model=SuccessResponse)
async def force_reset_session(x_api_key: Optional[str] = Header(None)):
    """
    Force reset the recorder state.

    Use for crash recovery when CMED crashes and recorder is stuck.
    """
    verify_api_key(x_api_key)

    if _controller is None:
        return SuccessResponse(
            success=True,
            data={"status": "no_controller"},
            message="Controller not initialized"
        )

    logger.warning("Force reset requested via API")

    try:
        result = await _controller.force_reset()

        return SuccessResponse(
            success=True,
            data={
                "status": result.get("status", "reset_complete"),
                "previous_patient_id": result.get("previous_patient_id"),
            },
            message=result.get("message", "Recorder state has been forcefully reset")
        )

    except Exception as e:
        logger.error(f"Force reset error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Legacy Endpoints (Backward Compatibility)
# ============================================================

@app.post("/trigger")
async def legacy_trigger(request: dict):
    """Legacy trigger endpoint for backward compatibility"""
    logger.warning("Legacy /trigger endpoint called - please migrate to /api/v1/session/start")

    # Convert to new format
    new_request = StartSessionRequest(
        patient=PatientInfo(
            id=request.get("patient_id", ""),
            name=request.get("patient_name", ""),
            age=int(request.get("age", 0)) if request.get("age") else 0,
            gender=request.get("gender", "")
        ),
        doctor=DoctorInfo(
            id=request.get("doctor_id", "DR_DEFAULT")
        ),
        hospital=HospitalInfo(
            id=request.get("hospital_id", "HOSP_DEFAULT")
        ),
        health_screening=HealthScreening(**request.get("health_screening", {})),
        callback=CallbackConfig(
            ner_webhook_url=request.get("ner_webhook_url", "http://localhost:3000/api/aimscribe/ner")
        )
    )

    return await start_session(new_request)


@app.post("/stop")
async def legacy_stop():
    """Legacy stop endpoint for backward compatibility"""
    logger.warning("Legacy /stop endpoint called - please migrate to /api/v1/session/stop")
    return await stop_session()


@app.get("/status")
async def legacy_status():
    """Legacy status endpoint for backward compatibility"""
    logger.warning("Legacy /status endpoint called - please migrate to /api/v1/session/status")
    return await get_session_status()


@app.post("/force-reset")
async def legacy_force_reset():
    """Legacy force-reset endpoint for backward compatibility"""
    logger.warning("Legacy /force-reset endpoint called - please migrate to /api/v1/session/force-reset")
    return await force_reset_session()

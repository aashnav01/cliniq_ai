"""
ClinIQ API — v4.0.0

Core AI:       Gemini 2.0 Flash (all clinical LLM tasks)
Voice STT:     Groq Whisper large-v3-turbo
Database:      MongoDB Atlas (motor async driver)
MCP Agent:     Natural language → MongoDB queries via Gemini
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from datetime import datetime
from pydantic import BaseModel
from typing import Optional, List
import json
from io import BytesIO

from config import settings
from gemini_service import gemini_service
from mongo_service import mongo_service
from fhir_router import router as fhir_router
from mongodb_mcp_agent import router as mcp_router


app = FastAPI(title="ClinIQ API", version="4.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_url,
        "https://cliniq-ai-1.onrender.com",
        "https://cliniq-frontend.onrender.com",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(fhir_router)
app.include_router(mcp_router)

# Redis (optional cache)
try:
    import redis
    redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    redis_client.ping()
    REDIS_AVAILABLE = True
except Exception:
    redis_client = None
    REDIS_AVAILABLE = False


# ── Startup: create MongoDB indexes ──────────────────────────────────────────

@app.on_event("startup")
async def startup_db():
    await mongo_service.ensure_indexes()


# ── Request models ───────────────────────────────────────────────────────────

class HandoverRequest(BaseModel):
    raw_notes: str
    shift_id: Optional[str] = None
    patient_id: Optional[str] = None

class SoapRequest(BaseModel):
    raw_notes: str
    shift_id: Optional[str] = None
    patient_id: Optional[str] = None

class DrugInteractionRequest(BaseModel):
    plan_text: str

class DdxRequest(BaseModel):
    clinical_presentation: str
    shift_id: Optional[str] = None
    patient_id: Optional[str] = None

class ReferralRequest(BaseModel):
    soap_data: dict
    specialty: str

class RapidModeRequest(BaseModel):
    brief_notes: str
    language: Optional[str] = "english"
    shift_id: Optional[str] = None

class FeedbackRequest(BaseModel):
    analysis_id: str
    value: str

class ShiftStartRequest(BaseModel):
    doctor_name: Optional[str] = "Doctor"
    specialty: Optional[str] = ""

class ShiftEndRequest(BaseModel):
    shift_id: str

class PatientCreateRequest(BaseModel):
    name: str
    mrn: Optional[str] = None
    dob: Optional[str] = None
    gender: Optional[str] = None
    weight_kg: Optional[float] = None
    allergies: Optional[List[str]] = []
    renal_function: Optional[str] = "normal"
    hepatic_function: Optional[str] = "normal"

class PrescriptionSafetyRequest(BaseModel):
    drugs: List[str]
    patient_id: Optional[str] = None
    shift_id: Optional[str] = None
    patient_context: Optional[dict] = {}

class ICD10Request(BaseModel):
    clinical_text: str


# ── Helper ───────────────────────────────────────────────────────────────────

async def save_analysis(analysis_type, input_text, output_data, processing_time_ms,
                        shift_id=None, patient_id=None):
    """Save an analysis to MongoDB and optionally cache in Redis."""
    doc = await mongo_service.save_analysis(
        analysis_type=analysis_type,
        input_text=input_text,
        output_data=output_data,
        processing_time_ms=processing_time_ms,
        shift_id=shift_id,
        patient_id=patient_id,
    )
    if REDIS_AVAILABLE:
        try:
            redis_client.setex(f"analysis:{doc['id']}", 3600, json.dumps(output_data, default=str))
        except Exception:
            pass
    return doc


# ── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "environment": settings.environment,
        "redis": REDIS_AVAILABLE,
        "llm_model": "gemini-2.5-flash",
        "stt_model": "groq-whisper-large-v3-turbo",
        "database": "mongodb-atlas",
        "mcp_agent": True,
        "fhir": True,
        "version": "4.0.0",
        "features": [
            "news2", "qsofa", "icd10", "prescription_safety",
            "discharge_pdf", "whisper", "timeline", "analytics",
            "mcp_agent", "gemini_flash"
        ]
    }


# ── Shift management ─────────────────────────────────────────────────────────

@app.post("/api/shift/start")
async def start_shift(request: ShiftStartRequest):
    shift = await mongo_service.create_shift(
        doctor_name=request.doctor_name,
        specialty=request.specialty,
    )
    return {"shift_id": shift["id"], "started_at": shift["started_at"]}


@app.post("/api/shift/end")
async def end_shift(request: ShiftEndRequest):
    shift = await mongo_service.get_shift(request.shift_id)
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")

    analyses = await mongo_service.get_shift_analyses(request.shift_id)
    total = len(analyses)
    by_type = {}
    for a in analyses:
        t = a.get("analysis_type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1

    avg_ms = int(sum(a.get("processing_time_ms", 0) or 0 for a in analyses) / total) if total else 0
    thumbs_up = sum(1 for a in analyses if a.get("feedback") == "up")
    thumbs_down = sum(1 for a in analyses if a.get("feedback") == "down")

    updated_shift = await mongo_service.end_shift(request.shift_id)
    started = shift.get("started_at", "")
    ended = updated_shift.get("ended_at", "")

    try:
        started_dt = datetime.fromisoformat(started) if isinstance(started, str) else started
        ended_dt = datetime.fromisoformat(ended) if isinstance(ended, str) else ended
        duration_mins = int((ended_dt - started_dt).total_seconds() / 60) if started_dt and ended_dt else 0
    except Exception:
        duration_mins = 0

    return {
        "shift_id": request.shift_id,
        "doctor_name": shift.get("doctor_name"),
        "specialty": shift.get("specialty"),
        "started_at": started,
        "ended_at": ended,
        "duration_minutes": duration_mins,
        "summary": {
            "total_analyses": total,
            "handovers": by_type.get("handover", 0),
            "soap_notes": by_type.get("soap", 0),
            "differentials": by_type.get("differential_diagnosis", 0),
            "rapid_notes": by_type.get("rapid", 0),
            "avg_processing_ms": avg_ms,
            "thumbs_up": thumbs_up,
            "thumbs_down": thumbs_down
        }
    }


@app.get("/api/shift/{shift_id}/history")
async def get_shift_history(shift_id: str):
    analyses = await mongo_service.get_shift_analyses(shift_id)
    return {
        "count": len(analyses),
        "analyses": [
            {
                "id": a.get("id"),
                "analysis_type": a.get("analysis_type"),
                "input_preview": (a.get("input_text") or "")[:100],
                "processing_time_ms": a.get("processing_time_ms"),
                "feedback": a.get("feedback"),
                "created_at": a.get("created_at")
            }
            for a in analyses
        ]
    }


@app.get("/api/shift/{shift_id}/discharge-summary")
async def get_discharge_summary_pdf(shift_id: str):
    """Generate and return a full PDF discharge summary for the shift."""
    shift = await mongo_service.get_shift(shift_id)
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")

    analyses = await mongo_service.get_shift_analyses(shift_id)
    prescriptions = await mongo_service.get_shift_prescriptions(shift_id)

    shift_data = {
        "doctor_name": shift.get("doctor_name"),
        "specialty": shift.get("specialty"),
        "started_at": shift.get("started_at"),
        "ended_at": shift.get("ended_at"),
        "analyses": [
            {
                "type": a.get("analysis_type"),
                "data": a.get("output_data"),
                "created_at": a.get("created_at")
            }
            for a in analyses
        ],
        "prescriptions": [
            {
                "drugs": p.get("drugs"),
                "safety_result": p.get("safety_result"),
                "created_at": p.get("created_at")
            }
            for p in prescriptions
        ]
    }

    try:
        summary_result = await gemini_service.generate_discharge_summary(shift_data)
        discharge_summary = summary_result.get("data", {})
    except Exception:
        discharge_summary = {}

    from pdf_service import generate_shift_pdf
    pdf_bytes = generate_shift_pdf(
        shift=shift,
        analyses=analyses,
        discharge_summary=discharge_summary,
        prescriptions=prescriptions
    )

    filename = f"ClinIQ_Shift_{shift_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ── Analytics ────────────────────────────────────────────────────────────────

@app.get("/api/analytics/shift")
async def get_analytics():
    """Aggregated metrics across all shifts."""
    return await mongo_service.get_all_analytics()


# ── Patient management ───────────────────────────────────────────────────────

@app.post("/api/patients")
async def create_patient(request: PatientCreateRequest):
    patient = await mongo_service.create_patient(
        name=request.name,
        mrn=request.mrn,
        dob=request.dob,
        gender=request.gender,
        weight_kg=request.weight_kg,
        allergies=request.allergies or [],
        renal_function=request.renal_function or "normal",
        hepatic_function=request.hepatic_function or "normal",
    )
    return patient


@app.get("/api/patients")
async def list_patients():
    patients = await mongo_service.list_patients()
    return patients


@app.get("/api/patients/{patient_id}")
async def get_patient(patient_id: str):
    p = await mongo_service.get_patient(patient_id)
    if not p:
        raise HTTPException(status_code=404, detail="Patient not found")
    return p


@app.get("/api/patient/{patient_id}/timeline")
async def get_patient_timeline(patient_id: str):
    """Chronological audit log of everything done for this patient."""
    patient = await mongo_service.get_patient(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    analyses, prescriptions = await mongo_service.get_patient_timeline(patient_id)

    timeline = []
    for a in analyses:
        timeline.append({
            "type": "analysis",
            "analysis_type": a.get("analysis_type"),
            "id": a.get("id"),
            "summary": _analysis_summary(a),
            "data": a.get("output_data"),
            "processing_time_ms": a.get("processing_time_ms"),
            "feedback": a.get("feedback"),
            "timestamp": a.get("created_at")
        })
    for p in prescriptions:
        safety = p.get("safety_result") or {}
        timeline.append({
            "type": "prescription",
            "id": p.get("id"),
            "drugs": p.get("drugs"),
            "overall_safety": safety.get("overall_safety", "unknown"),
            "has_critical_flags": bool(p.get("has_critical_flags")),
            "flags_count": len(safety.get("flags", [])),
            "timestamp": p.get("created_at")
        })

    timeline.sort(key=lambda x: x.get("timestamp") or "")

    return {
        "patient": {
            "id": patient.get("id"),
            "name": patient.get("name"),
            "mrn": patient.get("mrn"),
            "allergies": patient.get("allergies")
        },
        "timeline": timeline,
        "count": len(timeline)
    }


def _analysis_summary(a: dict) -> str:
    d = a.get("output_data") or {}
    t = a.get("analysis_type", "")
    if t == "soap":
        return (d.get("assessment") or d.get("subjective") or "SOAP note")[:120]
    if t == "handover":
        pts = d.get("patients", [])
        return f"{len(pts)} patient(s) handed over" if pts else "Handover note"
    if t == "differential_diagnosis":
        return f"DDx: {d.get('most_likely', 'See report')}"
    if t == "rapid":
        return (d.get("assessment") or "Rapid note")[:120]
    return f"{t} analysis"


# ── Feedback ─────────────────────────────────────────────────────────────────

@app.post("/api/feedback")
async def submit_feedback(request: FeedbackRequest):
    success = await mongo_service.update_feedback(request.analysis_id, request.value)
    if not success:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return {"success": True}


# ── Analysis reload ──────────────────────────────────────────────────────────

@app.get("/api/analyses/detail/{analysis_id}")
async def get_analysis(analysis_id: str):
    a = await mongo_service.get_analysis(analysis_id)
    if not a:
        raise HTTPException(status_code=404, detail="Not found")
    return {
        "id": a.get("id"),
        "analysis_type": a.get("analysis_type"),
        "input_text": a.get("input_text"),
        "data": a.get("output_data"),
        "processing_time_ms": a.get("processing_time_ms"),
        "feedback": a.get("feedback"),
        "created_at": a.get("created_at")
    }


@app.get("/api/analyses/{analysis_type}")
async def get_analyses(analysis_type: str, limit: int = 20):
    analyses = await mongo_service.get_analyses_by_type(analysis_type, limit)
    return {
        "count": len(analyses),
        "analyses": [
            {
                "id": a.get("id"),
                "input_preview": (a.get("input_text") or "")[:100],
                "processing_time_ms": a.get("processing_time_ms"),
                "feedback": a.get("feedback"),
                "created_at": a.get("created_at")
            }
            for a in analyses
        ]
    }


# ── Core Analysis Endpoints ──────────────────────────────────────────────────

@app.post("/api/analyze/handover")
async def analyze_handover(request: HandoverRequest):
    if not request.raw_notes.strip():
        raise HTTPException(status_code=400, detail="raw_notes cannot be empty")
    try:
        result = await gemini_service.process_handover(request.raw_notes)
        a = await save_analysis("handover", request.raw_notes, result["data"],
                                result["processing_time_ms"], request.shift_id, request.patient_id)
        return {"id": a["id"], "data": result["data"],
                "processing_time_ms": result["processing_time_ms"], "model": result["model"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analyze/soap")
async def analyze_soap(request: SoapRequest):
    if not request.raw_notes.strip():
        raise HTTPException(status_code=400, detail="raw_notes cannot be empty")
    try:
        result = await gemini_service.process_soap(request.raw_notes)
        icd_result = await gemini_service.suggest_icd10(request.raw_notes)
        result["data"]["icd10"] = icd_result.get("data", {})
        a = await save_analysis("soap", request.raw_notes, result["data"],
                                result["processing_time_ms"], request.shift_id, request.patient_id)
        return {"id": a["id"], "data": result["data"],
                "processing_time_ms": result["processing_time_ms"], "model": result["model"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analyze/drug-interactions")
async def analyze_drug_interactions(request: DrugInteractionRequest):
    if not request.plan_text.strip():
        raise HTTPException(status_code=400, detail="plan_text cannot be empty")
    try:
        result = await gemini_service.process_drug_interactions(request.plan_text)
        return {"data": result["data"], "processing_time_ms": result["processing_time_ms"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analyze/ddx")
async def analyze_ddx(request: DdxRequest):
    if not request.clinical_presentation.strip():
        raise HTTPException(status_code=400, detail="clinical_presentation cannot be empty")
    try:
        result = await gemini_service.process_differential_diagnosis(request.clinical_presentation)
        a = await save_analysis("differential_diagnosis", request.clinical_presentation,
                                result["data"], result["processing_time_ms"],
                                request.shift_id, request.patient_id)
        return {"id": a["id"], "data": result["data"],
                "processing_time_ms": result["processing_time_ms"], "model": result["model"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analyze/referral")
async def analyze_referral(request: ReferralRequest):
    if not request.specialty.strip():
        raise HTTPException(status_code=400, detail="specialty cannot be empty")
    try:
        result = await gemini_service.process_referral(request.soap_data, request.specialty)
        return {"data": result["data"], "processing_time_ms": result["processing_time_ms"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analyze/rapid")
async def analyze_rapid(request: RapidModeRequest):
    if not request.brief_notes.strip():
        raise HTTPException(status_code=400, detail="brief_notes cannot be empty")
    try:
        result = await gemini_service.process_rapid_mode(request.brief_notes, request.language)
        a = await save_analysis("rapid", request.brief_notes, result["data"],
                                result["processing_time_ms"], request.shift_id)
        return {"id": a["id"], "data": result["data"],
                "processing_time_ms": result["processing_time_ms"], "model": result["model"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analyze/prescription-safety")
async def analyze_prescription_safety(request: PrescriptionSafetyRequest):
    if not request.drugs:
        raise HTTPException(status_code=400, detail="drugs list cannot be empty")

    patient_context = dict(request.patient_context or {})
    if request.patient_id:
        patient = await mongo_service.get_patient(request.patient_id)
        if patient:
            patient_context.setdefault("allergies", patient.get("allergies") or [])
            patient_context.setdefault("weight_kg", patient.get("weight_kg"))
            patient_context.setdefault("renal_function", patient.get("renal_function"))
            patient_context.setdefault("hepatic_function", patient.get("hepatic_function"))

    try:
        result = await gemini_service.process_prescription_safety(request.drugs, patient_context)
        safety_data = result["data"]

        flags = safety_data.get("flags", [])
        has_critical = any(f.get("severity") == "critical" for f in flags)

        rx = await mongo_service.save_prescription(
            shift_id=request.shift_id,
            patient_id=request.patient_id,
            drugs=request.drugs,
            patient_context=patient_context,
            safety_result=safety_data,
            has_critical_flags=has_critical,
        )

        return {
            "id": rx["id"],
            "data": safety_data,
            "has_critical_flags": has_critical,
            "processing_time_ms": result["processing_time_ms"],
            "model": result["model"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analyze/icd10")
async def suggest_icd10(request: ICD10Request):
    if not request.clinical_text.strip():
        raise HTTPException(status_code=400, detail="clinical_text cannot be empty")
    try:
        result = await gemini_service.suggest_icd10(request.clinical_text)
        return {"data": result["data"], "processing_time_ms": result["processing_time_ms"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analyze/transcribe")
async def transcribe_audio(file: UploadFile = File(...), language: Optional[str] = Form(None)):
    """Transcribe audio using Groq Whisper. Accepts webm, ogg, mp3, wav, m4a.
    Pass language='hi' for Hindi, 'ta' for Tamil, 'te' for Telugu, 'bn' for Bengali, 'mr' for Marathi.
    Leave empty for auto-detection (recommended for English).
    """
    try:
        audio_bytes = await file.read()
        result = await gemini_service.transcribe_audio(
            audio_bytes,
            file.filename or "recording.webm",
            language=language or None
        )
        return {
            "data": result["data"],
            "processing_time_ms": result["processing_time_ms"],
            "model": result["model"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

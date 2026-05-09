from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session as DBSession
from datetime import datetime
from pydantic import BaseModel
from typing import Optional
import json

from config import settings
from database import get_db, init_db
from models import Analysis, ShiftSession
from groq_service import groq_service

init_db()

app = FastAPI(title="ClinIQ API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    import redis
    redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    redis_client.ping()
    REDIS_AVAILABLE = True
except Exception:
    redis_client = None
    REDIS_AVAILABLE = False


# ── Request models ──

class HandoverRequest(BaseModel):
    raw_notes: str
    shift_id: Optional[int] = None

class SoapRequest(BaseModel):
    raw_notes: str
    shift_id: Optional[int] = None

class DrugInteractionRequest(BaseModel):
    plan_text: str

class DdxRequest(BaseModel):
    clinical_presentation: str
    shift_id: Optional[int] = None

class ReferralRequest(BaseModel):
    soap_data: dict
    specialty: str

class RapidModeRequest(BaseModel):
    brief_notes: str
    language: Optional[str] = "english"
    shift_id: Optional[int] = None

class FeedbackRequest(BaseModel):
    analysis_id: int
    value: str

class ShiftStartRequest(BaseModel):
    doctor_name: Optional[str] = "Doctor"
    specialty: Optional[str] = ""

class ShiftEndRequest(BaseModel):
    shift_id: int


# ── Helpers ──

def save_analysis(db, analysis_type, input_text, output_data, processing_time_ms, shift_id=None):
    a = Analysis(
        shift_id=shift_id,
        input_text=input_text,
        output_data=output_data,
        analysis_type=analysis_type,
        processing_time_ms=processing_time_ms
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    if REDIS_AVAILABLE:
        try:
            redis_client.setex(f"analysis:{a.id}", 3600, json.dumps(output_data, default=str))
        except Exception:
            pass
    return a


# ── Health ──

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "environment": settings.environment,
        "redis": REDIS_AVAILABLE,
        "model": settings.groq_model
    }


# ── Shift management ──

@app.post("/api/shift/start")
async def start_shift(request: ShiftStartRequest, db: DBSession = Depends(get_db)):
    shift = ShiftSession(
        doctor_name=request.doctor_name,
        specialty=request.specialty,
        started_at=datetime.utcnow()
    )
    db.add(shift)
    db.commit()
    db.refresh(shift)
    return {"shift_id": shift.id, "started_at": shift.started_at.isoformat()}


@app.post("/api/shift/end")
async def end_shift(request: ShiftEndRequest, db: DBSession = Depends(get_db)):
    shift = db.query(ShiftSession).filter(ShiftSession.id == request.shift_id).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")

    analyses = db.query(Analysis).filter(Analysis.shift_id == request.shift_id).all()
    total = len(analyses)
    by_type = {}
    for a in analyses:
        by_type[a.analysis_type] = by_type.get(a.analysis_type, 0) + 1

    avg_ms = int(sum(a.processing_time_ms or 0 for a in analyses) / total) if total else 0
    thumbs_up = sum(1 for a in analyses if a.feedback == "up")
    thumbs_down = sum(1 for a in analyses if a.feedback == "down")

    shift.ended_at = datetime.utcnow()
    db.commit()

    duration_mins = int((shift.ended_at - shift.started_at).total_seconds() / 60)

    return {
        "shift_id": shift.id,
        "doctor_name": shift.doctor_name,
        "specialty": shift.specialty,
        "started_at": shift.started_at.isoformat(),
        "ended_at": shift.ended_at.isoformat(),
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
async def get_shift_history(shift_id: int, db: DBSession = Depends(get_db)):
    analyses = db.query(Analysis).filter(
        Analysis.shift_id == shift_id
    ).order_by(Analysis.created_at.desc()).all()
    return {
        "count": len(analyses),
        "analyses": [
            {
                "id": a.id,
                "analysis_type": a.analysis_type,
                "input_preview": (a.input_text or "")[:100],
                "processing_time_ms": a.processing_time_ms,
                "feedback": a.feedback,
                "created_at": a.created_at.isoformat() if a.created_at else None
            }
            for a in analyses
        ]
    }


# ── Feedback ──

@app.post("/api/feedback")
async def submit_feedback(request: FeedbackRequest, db: DBSession = Depends(get_db)):
    a = db.query(Analysis).filter(Analysis.id == request.analysis_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Analysis not found")
    a.feedback = request.value
    db.commit()
    return {"success": True}


# ── Analysis reload ──

@app.get("/api/analyses/detail/{analysis_id}")
async def get_analysis(analysis_id: int, db: DBSession = Depends(get_db)):
    a = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Not found")
    return {
        "id": a.id,
        "analysis_type": a.analysis_type,
        "input_text": a.input_text,
        "data": a.output_data,
        "processing_time_ms": a.processing_time_ms,
        "feedback": a.feedback,
        "created_at": a.created_at.isoformat() if a.created_at else None
    }


@app.get("/api/analyses/{analysis_type}")
async def get_analyses(analysis_type: str, limit: int = 20, db: DBSession = Depends(get_db)):
    analyses = db.query(Analysis).filter(
        Analysis.analysis_type == analysis_type
    ).order_by(Analysis.created_at.desc()).limit(limit).all()
    return {
        "count": len(analyses),
        "analyses": [
            {
                "id": a.id,
                "input_preview": (a.input_text or "")[:100],
                "processing_time_ms": a.processing_time_ms,
                "feedback": a.feedback,
                "created_at": a.created_at.isoformat() if a.created_at else None
            }
            for a in analyses
        ]
    }


# ── Analysis endpoints ──

@app.post("/api/analyze/handover")
async def analyze_handover(request: HandoverRequest, db: DBSession = Depends(get_db)):
    if not request.raw_notes.strip():
        raise HTTPException(status_code=400, detail="raw_notes cannot be empty")
    try:
        result = await groq_service.process_handover(request.raw_notes)
        a = save_analysis(db, "handover", request.raw_notes, result["data"], result["processing_time_ms"], request.shift_id)
        return {"id": a.id, "data": result["data"], "processing_time_ms": result["processing_time_ms"], "model": result["model"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analyze/soap")
async def analyze_soap(request: SoapRequest, db: DBSession = Depends(get_db)):
    if not request.raw_notes.strip():
        raise HTTPException(status_code=400, detail="raw_notes cannot be empty")
    try:
        result = await groq_service.process_soap(request.raw_notes)
        a = save_analysis(db, "soap", request.raw_notes, result["data"], result["processing_time_ms"], request.shift_id)
        return {"id": a.id, "data": result["data"], "processing_time_ms": result["processing_time_ms"], "model": result["model"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analyze/drug-interactions")
async def analyze_drug_interactions(request: DrugInteractionRequest):
    if not request.plan_text.strip():
        raise HTTPException(status_code=400, detail="plan_text cannot be empty")
    try:
        result = await groq_service.process_drug_interactions(request.plan_text)
        return {"data": result["data"], "processing_time_ms": result["processing_time_ms"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analyze/ddx")
async def analyze_ddx(request: DdxRequest, db: DBSession = Depends(get_db)):
    if not request.clinical_presentation.strip():
        raise HTTPException(status_code=400, detail="clinical_presentation cannot be empty")
    try:
        result = await groq_service.process_differential_diagnosis(request.clinical_presentation)
        a = save_analysis(db, "differential_diagnosis", request.clinical_presentation, result["data"], result["processing_time_ms"], request.shift_id)
        return {"id": a.id, "data": result["data"], "processing_time_ms": result["processing_time_ms"], "model": result["model"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analyze/referral")
async def analyze_referral(request: ReferralRequest):
    if not request.specialty.strip():
        raise HTTPException(status_code=400, detail="specialty cannot be empty")
    try:
        result = await groq_service.process_referral(request.soap_data, request.specialty)
        return {"data": result["data"], "processing_time_ms": result["processing_time_ms"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analyze/rapid")
async def analyze_rapid(request: RapidModeRequest, db: DBSession = Depends(get_db)):
    if not request.brief_notes.strip():
        raise HTTPException(status_code=400, detail="brief_notes cannot be empty")
    try:
        result = await groq_service.process_rapid_mode(request.brief_notes, request.language)
        a = save_analysis(db, "rapid", request.brief_notes, result["data"], result["processing_time_ms"], request.shift_id)
        return {"id": a.id, "data": result["data"], "processing_time_ms": result["processing_time_ms"], "model": result["model"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

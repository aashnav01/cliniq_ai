"""
fhir_router.py — FHIR R4 endpoints for ClinIQ (MongoDB version)
Converts ClinIQ analysis outputs to standard FHIR resources.

Endpoints:
  GET  /fhir/metadata                      → CapabilityStatement
  POST /fhir/Patient                       → create Patient
  GET  /fhir/Patient/{id}                  → read Patient
  POST /fhir/Encounter                     → create Encounter (from shift)
  GET  /fhir/Encounter/{id}               → read Encounter
  POST /fhir/Composition                   → create SOAP note as DocumentReference
  GET  /fhir/Composition/{id}             → read Composition
  POST /fhir/DiagnosticReport             → create DDx report
  GET  /fhir/DiagnosticReport/{id}        → read DiagnosticReport
  GET  /fhir/analyses/{id}/fhir           → convert any saved analysis to FHIR
"""

from fastapi import APIRouter, HTTPException
from mongo_service import mongo_service
from fhir_service import (
    build_capability_statement,
    analysis_to_fhir_from_dict,
    shift_to_encounter_from_dict,
    build_patient,
    get_fhir_store,
    save_fhir_resource,
)
from pydantic import BaseModel
from typing import Optional
import uuid

router = APIRouter(prefix="/fhir", tags=["FHIR R4"])


# ── Capability Statement ──────────────────────────────────────────────────────

@router.get("/metadata")
async def capability_statement():
    """FHIR CapabilityStatement — advertises what this server supports."""
    return build_capability_statement()


# ── Patient ──────────────────────────────────────────────────────────────────

class PatientCreateRequest(BaseModel):
    family_name: str
    given_name: str
    birth_date: Optional[str] = None          # YYYY-MM-DD
    gender: Optional[str] = "unknown"         # male | female | other | unknown
    identifier: Optional[str] = None          # e.g. MRN


@router.post("/Patient", status_code=201)
async def create_patient(req: PatientCreateRequest):
    """Create a minimal FHIR Patient resource (stored in-memory)."""
    resource = build_patient(
        family=req.family_name,
        given=req.given_name,
        birth_date=req.birth_date,
        gender=req.gender,
        identifier=req.identifier,
    )
    save_fhir_resource("Patient", resource["id"], resource)
    return resource


@router.get("/Patient/{patient_id}")
async def read_patient(patient_id: str):
    store = get_fhir_store()
    resource = store.get("Patient", {}).get(patient_id)
    if not resource:
        raise HTTPException(status_code=404, detail=f"Patient/{patient_id} not found")
    return resource


# ── Encounter (from ShiftSession) ─────────────────────────────────────────────

@router.post("/Encounter", status_code=201)
async def create_encounter(shift_id: str):
    """Convert a ClinIQ ShiftSession into a FHIR Encounter."""
    shift = await mongo_service.get_shift(shift_id)
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    resource = shift_to_encounter_from_dict(shift)
    save_fhir_resource("Encounter", resource["id"], resource)
    return resource


@router.get("/Encounter/{encounter_id}")
async def read_encounter(encounter_id: str):
    store = get_fhir_store()
    resource = store.get("Encounter", {}).get(encounter_id)
    if not resource:
        raise HTTPException(status_code=404, detail=f"Encounter/{encounter_id} not found")
    return resource


# ── Composition (SOAP note) ───────────────────────────────────────────────────

@router.post("/Composition", status_code=201)
async def create_composition(analysis_id: str):
    """Convert a SOAP analysis into a FHIR Composition (clinical document)."""
    analysis = await mongo_service.get_analysis(analysis_id)
    if not analysis or analysis.get("analysis_type") != "soap":
        raise HTTPException(status_code=404, detail="SOAP analysis not found")
    resource = analysis_to_fhir_from_dict(analysis)
    save_fhir_resource("Composition", resource["id"], resource)
    return resource


@router.get("/Composition/{composition_id}")
async def read_composition(composition_id: str):
    store = get_fhir_store()
    resource = store.get("Composition", {}).get(composition_id)
    if not resource:
        raise HTTPException(status_code=404, detail=f"Composition/{composition_id} not found")
    return resource


# ── DiagnosticReport (DDx) ────────────────────────────────────────────────────

@router.post("/DiagnosticReport", status_code=201)
async def create_diagnostic_report(analysis_id: str):
    """Convert a DDx analysis into a FHIR DiagnosticReport."""
    analysis = await mongo_service.get_analysis(analysis_id)
    if not analysis or analysis.get("analysis_type") != "differential_diagnosis":
        raise HTTPException(status_code=404, detail="DDx analysis not found")
    resource = analysis_to_fhir_from_dict(analysis)
    save_fhir_resource("DiagnosticReport", resource["id"], resource)
    return resource


@router.get("/DiagnosticReport/{report_id}")
async def read_diagnostic_report(report_id: str):
    store = get_fhir_store()
    resource = store.get("DiagnosticReport", {}).get(report_id)
    if not resource:
        raise HTTPException(status_code=404, detail=f"DiagnosticReport/{report_id} not found")
    return resource


# ── Generic: convert any saved analysis to FHIR ──────────────────────────────

@router.get("/analyses/{analysis_id}/fhir")
async def get_analysis_as_fhir(analysis_id: str):
    """
    Convert any saved ClinIQ analysis to its FHIR representation on the fly.
    Does NOT persist to the FHIR store — use the type-specific POST endpoints for that.
    """
    analysis = await mongo_service.get_analysis(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    try:
        return analysis_to_fhir_from_dict(analysis)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


# ── Bundle: export all analyses for a shift as FHIR Bundle ───────────────────

@router.get("/shift/{shift_id}/bundle")
async def export_shift_as_bundle(shift_id: str):
    """
    Export an entire shift (encounter + all analyses) as a FHIR Bundle.
    Useful for EHR handoff.
    """
    shift = await mongo_service.get_shift(shift_id)
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")

    analyses = await mongo_service.get_shift_analyses(shift_id)
    encounter = shift_to_encounter_from_dict(shift)

    entries = [{"fullUrl": f"urn:uuid:{encounter['id']}", "resource": encounter}]
    for a in analyses:
        try:
            resource = analysis_to_fhir_from_dict(a)
            entries.append({"fullUrl": f"urn:uuid:{resource['id']}", "resource": resource})
        except ValueError:
            pass  # skip analysis types not yet mapped

    started_at = shift.get("started_at", "")
    if hasattr(started_at, "isoformat"):
        started_at = started_at.isoformat() + "Z"

    bundle = {
        "resourceType": "Bundle",
        "id": str(uuid.uuid4()),
        "type": "collection",
        "timestamp": str(started_at),
        "entry": entries,
    }
    return bundle

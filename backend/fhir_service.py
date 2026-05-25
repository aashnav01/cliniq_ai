"""
fhir_service.py — Converts ClinIQ internal data structures to FHIR R4 resources.

Supported mappings:
  Analysis (soap)                   → Composition
  Analysis (differential_diagnosis) → DiagnosticReport
  Analysis (handover)               → DocumentReference
  Analysis (rapid)                  → DocumentReference
  Analysis (drug interactions)      → MedicationStatement list inside DiagnosticReport
  ShiftSession                      → Encounter
  Patient dict                      → Patient
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

# ── In-memory FHIR store (replace with a real FHIR server / DB in production) ──
_fhir_store: dict[str, dict[str, dict]] = {}


def get_fhir_store() -> dict:
    return _fhir_store


def save_fhir_resource(resource_type: str, resource_id: str, resource: dict):
    if resource_type not in _fhir_store:
        _fhir_store[resource_type] = {}
    _fhir_store[resource_type][resource_id] = resource


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _dt_iso(dt: Optional[datetime]) -> str:
    if dt is None:
        return _now_iso()
    if dt.tzinfo is None:
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ── CapabilityStatement ───────────────────────────────────────────────────────

def build_capability_statement() -> dict:
    return {
        "resourceType": "CapabilityStatement",
        "id": "cliniq-fhir-capability",
        "status": "active",
        "date": _now_iso(),
        "kind": "instance",
        "software": {"name": "ClinIQ FHIR Adapter", "version": "1.0.0"},
        "fhirVersion": "4.0.1",
        "format": ["json"],
        "rest": [
            {
                "mode": "server",
                "resource": [
                    {"type": "Patient",            "interaction": [{"code": "read"}, {"code": "create"}]},
                    {"type": "Encounter",           "interaction": [{"code": "read"}, {"code": "create"}]},
                    {"type": "Composition",         "interaction": [{"code": "read"}, {"code": "create"}]},
                    {"type": "DiagnosticReport",    "interaction": [{"code": "read"}, {"code": "create"}]},
                    {"type": "DocumentReference",   "interaction": [{"code": "read"}, {"code": "create"}]},
                    {"type": "MedicationStatement", "interaction": [{"code": "read"}]},
                    {"type": "Bundle",              "interaction": [{"code": "read"}]},
                ],
            }
        ],
    }


# ── Patient ───────────────────────────────────────────────────────────────────

def build_patient(
    family: str,
    given: str,
    birth_date: Optional[str] = None,
    gender: str = "unknown",
    identifier: Optional[str] = None,
) -> dict:
    resource: dict = {
        "resourceType": "Patient",
        "id": str(uuid.uuid4()),
        "name": [{"use": "official", "family": family, "given": [given]}],
        "gender": gender,
    }
    if birth_date:
        resource["birthDate"] = birth_date
    if identifier:
        resource["identifier"] = [
            {
                "use": "usual",
                "system": "urn:cliniq:mrn",
                "value": identifier,
            }
        ]
    return resource


# ── Encounter (ShiftSession) ──────────────────────────────────────────────────

def shift_to_encounter(shift) -> dict:
    """Convert a ClinIQ ShiftSession SQLAlchemy object to a FHIR Encounter."""
    period: dict = {"start": _dt_iso(shift.started_at)}
    status = "in-progress"
    if shift.ended_at:
        period["end"] = _dt_iso(shift.ended_at)
        status = "finished"

    return {
        "resourceType": "Encounter",
        "id": str(uuid.uuid4()),
        "status": status,
        "class": {
            "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
            "code": "AMB",
            "display": "ambulatory",
        },
        "type": [
            {
                "coding": [
                    {
                        "system": "http://snomed.info/sct",
                        "code": "11429006",
                        "display": "Consultation",
                    }
                ]
            }
        ],
        "participant": [
            {
                "individual": {
                    "display": shift.doctor_name or "Unknown Doctor",
                    "type": shift.specialty or "General",
                }
            }
        ],
        "period": period,
        "meta": {"source": "cliniq", "versionId": "1"},
    }


# ── Analysis → FHIR dispatcher ────────────────────────────────────────────────

def analysis_to_fhir(analysis) -> dict:
    """
    Route a ClinIQ Analysis to the appropriate FHIR resource builder.
    Raises ValueError for unmapped analysis types.
    """
    dispatch = {
        "soap": _soap_to_composition,
        "differential_diagnosis": _ddx_to_diagnostic_report,
        "handover": _handover_to_document_reference,
        "rapid": _rapid_to_document_reference,
        "drug_interaction": _drug_interaction_to_diagnostic_report,
    }
    builder = dispatch.get(analysis.analysis_type)
    if not builder:
        raise ValueError(f"No FHIR mapping for analysis type: {analysis.analysis_type}")
    return builder(analysis)


# ── SOAP → Composition ────────────────────────────────────────────────────────

def _soap_to_composition(analysis) -> dict:
    data = analysis.output_data or {}
    created = _dt_iso(analysis.created_at)

    sections = []
    section_map = {
        "subjective":  ("Subjective",  "10164-2", "History of Present Illness"),
        "objective":   ("Objective",   "29545-1", "Physical Findings"),
        "assessment":  ("Assessment",  "51848-0", "Assessment"),
        "plan":        ("Plan",        "18776-5", "Plan of Care"),
    }
    for key, (title, loinc_code, loinc_display) in section_map.items():
        content = data.get(key, "")
        if content:
            sections.append({
                "title": title,
                "code": {
                    "coding": [
                        {
                            "system": "http://loinc.org",
                            "code": loinc_code,
                            "display": loinc_display,
                        }
                    ]
                },
                "text": {
                    "status": "generated",
                    "div": f"<div xmlns='http://www.w3.org/1999/xhtml'>{content}</div>",
                },
            })

    return {
        "resourceType": "Composition",
        "id": str(uuid.uuid4()),
        "status": "final",
        "type": {
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": "11488-4",
                    "display": "Consult note",
                }
            ]
        },
        "date": created,
        "title": "SOAP Note",
        "section": sections,
        "meta": {
            "source": "cliniq",
            "tag": [{"system": "urn:cliniq:analysis", "code": str(analysis.id)}],
        },
    }


# ── DDx → DiagnosticReport ────────────────────────────────────────────────────

def _ddx_to_diagnostic_report(analysis) -> dict:
    data = analysis.output_data or {}
    created = _dt_iso(analysis.created_at)

    # ClinIQ typically returns a list of differentials
    differentials = data.get("differentials", data.get("diagnoses", []))
    conclusions = []
    coded_diagnoses = []

    for item in differentials:
        if isinstance(item, dict):
            name = item.get("diagnosis", item.get("name", str(item)))
            probability = item.get("probability", item.get("likelihood", ""))
        else:
            name = str(item)
            probability = ""

        text = f"{name} ({probability})" if probability else name
        conclusions.append(text)
        coded_diagnoses.append({
            "coding": [
                {
                    "system": "http://snomed.info/sct",
                    "display": name,
                }
            ],
            "text": text,
        })

    return {
        "resourceType": "DiagnosticReport",
        "id": str(uuid.uuid4()),
        "status": "final",
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/v2-0074",
                        "code": "GE",
                        "display": "General",
                    }
                ]
            }
        ],
        "code": {
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": "29308-4",
                    "display": "Diagnosis",
                }
            ],
            "text": "Differential Diagnosis",
        },
        "effectiveDateTime": created,
        "issued": created,
        "conclusion": " | ".join(conclusions) if conclusions else data.get("summary", ""),
        "conclusionCode": coded_diagnoses,
        "meta": {
            "source": "cliniq",
            "tag": [{"system": "urn:cliniq:analysis", "code": str(analysis.id)}],
        },
    }


# ── Handover → DocumentReference ──────────────────────────────────────────────

def _handover_to_document_reference(analysis) -> dict:
    data = analysis.output_data or {}
    created = _dt_iso(analysis.created_at)

    # Flatten handover data into readable text
    content_text = _flatten_dict_to_text(data)

    return {
        "resourceType": "DocumentReference",
        "id": str(uuid.uuid4()),
        "status": "current",
        "type": {
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": "34745-0",
                    "display": "Nurse Handoff note",
                }
            ],
            "text": "Clinical Handover Note",
        },
        "date": created,
        "description": "ClinIQ AI-generated handover note",
        "content": [
            {
                "attachment": {
                    "contentType": "text/plain",
                    "language": "en",
                    "data": _text_to_b64(content_text),
                    "title": "Handover Note",
                    "creation": created,
                }
            }
        ],
        "meta": {
            "source": "cliniq",
            "tag": [{"system": "urn:cliniq:analysis", "code": str(analysis.id)}],
        },
    }


# ── Rapid note → DocumentReference ───────────────────────────────────────────

def _rapid_to_document_reference(analysis) -> dict:
    data = analysis.output_data or {}
    created = _dt_iso(analysis.created_at)
    content_text = _flatten_dict_to_text(data)

    return {
        "resourceType": "DocumentReference",
        "id": str(uuid.uuid4()),
        "status": "current",
        "type": {
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": "11506-3",
                    "display": "Progress note",
                }
            ],
            "text": "Rapid Clinical Note",
        },
        "date": created,
        "description": "ClinIQ AI-generated rapid note",
        "content": [
            {
                "attachment": {
                    "contentType": "text/plain",
                    "language": "en",
                    "data": _text_to_b64(content_text),
                    "title": "Rapid Note",
                    "creation": created,
                }
            }
        ],
        "meta": {
            "source": "cliniq",
            "tag": [{"system": "urn:cliniq:analysis", "code": str(analysis.id)}],
        },
    }


# ── Drug interaction → DiagnosticReport ──────────────────────────────────────

def _drug_interaction_to_diagnostic_report(analysis) -> dict:
    data = analysis.output_data or {}
    created = _dt_iso(analysis.created_at)

    interactions = data.get("interactions", [])
    conclusion_parts = []
    for ix in interactions:
        if isinstance(ix, dict):
            drugs = ix.get("drugs", ix.get("pair", ""))
            severity = ix.get("severity", "")
            desc = ix.get("description", ix.get("interaction", ""))
            conclusion_parts.append(f"{drugs} [{severity}]: {desc}")
        else:
            conclusion_parts.append(str(ix))

    return {
        "resourceType": "DiagnosticReport",
        "id": str(uuid.uuid4()),
        "status": "final",
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/v2-0074",
                        "code": "PH",
                        "display": "Pharmacy",
                    }
                ]
            }
        ],
        "code": {
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": "56445-0",
                    "display": "Medication summary",
                }
            ],
            "text": "Drug Interaction Analysis",
        },
        "effectiveDateTime": created,
        "issued": created,
        "conclusion": "\n".join(conclusion_parts) if conclusion_parts else data.get("summary", "No interactions detected"),
        "meta": {
            "source": "cliniq",
            "tag": [{"system": "urn:cliniq:analysis", "code": str(analysis.id)}],
        },
    }


# ── Utilities ─────────────────────────────────────────────────────────────────

def _flatten_dict_to_text(d: dict, indent: int = 0) -> str:
    lines = []
    for k, v in d.items():
        prefix = "  " * indent
        if isinstance(v, dict):
            lines.append(f"{prefix}{k.upper()}:")
            lines.append(_flatten_dict_to_text(v, indent + 1))
        elif isinstance(v, list):
            lines.append(f"{prefix}{k.upper()}:")
            for item in v:
                if isinstance(item, dict):
                    lines.append(_flatten_dict_to_text(item, indent + 1))
                else:
                    lines.append(f"{prefix}  - {item}")
        else:
            lines.append(f"{prefix}{k}: {v}")
    return "\n".join(lines)


def _text_to_b64(text: str) -> str:
    import base64
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


# ── Dict-based wrappers (for MongoDB documents) ──────────────────────────────

class _DictProxy:
    """Wraps a dict so attribute access works like an ORM model."""
    def __init__(self, d: dict):
        self._d = d
    def __getattr__(self, name):
        if name.startswith("_"):
            return super().__getattribute__(name)
        return self._d.get(name)


def analysis_to_fhir_from_dict(analysis_dict: dict) -> dict:
    """Convert a MongoDB analysis document to FHIR."""
    return analysis_to_fhir(_DictProxy(analysis_dict))


def shift_to_encounter_from_dict(shift_dict: dict) -> dict:
    """Convert a MongoDB shift document to FHIR Encounter."""
    return shift_to_encounter(_DictProxy(shift_dict))


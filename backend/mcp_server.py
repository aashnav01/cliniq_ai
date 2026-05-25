"""
ClinIQ MCP Server
=================
Exposes ClinIQ's clinical AI capabilities as MCP tools for the
Prompt Opinion platform (Agents Assemble Hackathon).

Tools:
  1. generate_soap_note         - Convert raw notes → structured SOAP note
  2. check_drug_interactions    - Scan a treatment plan for dangerous combos
  3. differential_diagnosis     - Generate ranked DDx from clinical presentation
  4. parse_shift_handover       - Parse chaotic handover notes → structured cards
  5. rapid_soap_multilingual    - Expand brief/multilingual notes → full SOAP

Run:
  pip install fastmcp groq python-dotenv
  python mcp_server.py
"""

import os
import json
import time
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from groq import Groq

load_dotenv()

# ── Groq client ──────────────────────────────────────────────────────────────

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL   = os.getenv("GROQ_MODEL", "llama3-70b-8192")

client = Groq(api_key=GROQ_API_KEY)


def _call(system_prompt: str, user_content: str, max_tokens: int = 2000) -> str:
    completion = client.chat.completions.create(
        model=GROQ_MODEL,
        max_tokens=max_tokens,
        messages=[
            {"role": "system",  "content": system_prompt},
            {"role": "user",    "content": user_content},
        ],
    )
    return completion.choices[0].message.content


def _parse(text: str) -> dict:
    clean = text.replace("```json", "").replace("```", "").strip()
    return json.loads(clean)


# ── MCP server ────────────────────────────────────────────────────────────────

mcp = FastMCP("ClinIQ")


# ── Tool 1: SOAP Note Generator ───────────────────────────────────────────────

@mcp.tool()
def generate_soap_note(
    raw_notes: str,
    patient_id: str | None = None,
) -> dict:
    """
    Convert raw, unstructured clinical consultation notes into a professional
    SOAP (Subjective / Objective / Assessment / Plan) note.

    Also detects red-flag symptoms and suggests generic medication alternatives.

    Args:
        raw_notes:  Raw text the doctor jotted down during the encounter.
        patient_id: Optional FHIR patient ID for context (SHARP extension).

    Returns:
        dict with keys: subjective, objective, assessment, plan, red_flags
    """
    context = f"[Patient ID: {patient_id}]\n" if patient_id else ""

    system = """You are a clinical AI assistant. Convert raw consultation notes to SOAP format.
Return ONLY valid JSON:
{
  "subjective": "Chief complaint and history",
  "objective": "Vital signs and exam findings",
  "assessment": "Clinical impression",
  "plan": "Management and follow-up",
  "red_flags": [
    {
      "severity": "critical | warning | watch",
      "title": "Short title",
      "explanation": "Why this is a concern and what to do",
      "icon": "emoji"
    }
  ]
}
Sort red_flags: critical first. Return empty array if none."""

    try:
        text = _call(system, context + raw_notes, max_tokens=2000)
        return _parse(text)
    except Exception as e:
        return {"error": str(e), "raw": text if "text" in dir() else ""}


# ── Tool 2: Drug Interaction Checker ─────────────────────────────────────────

@mcp.tool()
def check_drug_interactions(
    plan_text: str,
    patient_id: str | None = None,
) -> dict:
    """
    Extract all medications from a treatment plan and check for dangerous
    drug-drug interactions or prescribing concerns.

    Args:
        plan_text:  Free-text treatment plan or medication list.
        patient_id: Optional FHIR patient ID for context (SHARP extension).

    Returns:
        dict with keys: medications_found (list), interactions (list), notes (str)
    """
    context = f"[Patient ID: {patient_id}]\n" if patient_id else ""

    system = """You are a clinical pharmacology AI. Extract all medications from the plan
text and check for interactions. Return ONLY valid JSON:
{
  "medications_found": ["drug1", "drug2"],
  "interactions": [
    {
      "drugs": ["drug1", "drug2"],
      "severity": "critical | warning | watch",
      "description": "What the interaction is and what to do about it"
    }
  ],
  "notes": "Any other prescribing concerns"
}
Return empty interactions array if none found."""

    try:
        text = _call(system, f"{context}Check medications in this plan:\n{plan_text}", max_tokens=1000)
        return _parse(text)
    except Exception as e:
        return {"medications_found": [], "interactions": [], "notes": str(e)}


# ── Tool 3: Differential Diagnosis ───────────────────────────────────────────

@mcp.tool()
def differential_diagnosis(
    clinical_presentation: str,
    patient_id: str | None = None,
) -> dict:
    """
    Generate a ranked list of differential diagnoses from demographics,
    vitals, and presenting symptoms. Highlights critical exclusions and
    suggests confirmatory / rule-out investigations.

    Args:
        clinical_presentation: Free-text description of the patient's
                               demographics, vitals, and presenting symptoms.
        patient_id:            Optional FHIR patient ID (SHARP extension).

    Returns:
        dict with keys: chief_complaint, differentials (ranked list),
                        most_likely, critical_exclusions
    """
    context = f"[Patient ID: {patient_id}]\n" if patient_id else ""

    system = """You are a clinical AI assistant. Generate ranked differential diagnoses.
Return ONLY valid JSON:
{
  "chief_complaint": "Summary of presentation",
  "differentials": [
    {
      "rank": 1,
      "diagnosis": "Diagnosis name",
      "confidence": 85,
      "reasoning": "Plain-language explanation",
      "confirm_tests": ["Test 1", "Test 2"],
      "rule_out_tests": ["Test A"],
      "red_flag": "Specific warning or null"
    }
  ],
  "most_likely": "Most likely diagnosis name",
  "critical_exclusions": ["Life-threatening condition to exclude"]
}
Rank by likelihood. Confidence 0-100."""

    try:
        text = _call(system, context + clinical_presentation, max_tokens=2500)
        return _parse(text)
    except Exception as e:
        return {"error": str(e)}


# ── Tool 4: Shift Handover Parser ─────────────────────────────────────────────

@mcp.tool()
def parse_shift_handover(raw_notes: str) -> dict:
    """
    Parse chaotic, stream-of-consciousness shift handover notes into
    structured patient cards sorted by urgency (critical → high → stable).

    Args:
        raw_notes: Raw handover text (e.g. "Bed 4 Mr Patel chest pain...
                   Bed 5 DKA sugars dropping...")

    Returns:
        dict with key: patients (list of structured patient cards)
    """
    system = """You are a clinical AI assistant. Parse raw shift handover notes and return ONLY valid JSON:
{
  "patients": [
    {
      "name": "Patient name/identifier",
      "age": "age if available",
      "bed": "bed/room if mentioned",
      "urgency": "critical | high | stable",
      "summary": "One-sentence status summary",
      "events": "Key events from previous shift",
      "medications": "Active medications mentioned",
      "watchFor": "What to monitor"
    }
  ]
}
Sort by urgency: critical first, then high, then stable."""

    try:
        text = _call(system, raw_notes, max_tokens=1500)
        return _parse(text)
    except Exception as e:
        return {"patients": [], "error": str(e)}


# ── Tool 5: Rapid Multilingual SOAP ──────────────────────────────────────────

@mcp.tool()
def rapid_soap_multilingual(
    brief_notes: str,
    language: str = "english",
    patient_id: str | None = None,
) -> dict:
    """
    Expand very brief clinical notes (even in regional languages like Hindi,
    Tamil, Telugu) into a full structured SOAP note. Also generates a
    patient-friendly summary in the original language.

    Args:
        brief_notes: Short, shorthand, or multilingual clinical notes.
        language:    Language of the input (default: "english").
                     Supports: hindi, tamil, telugu, bengali, marathi, etc.
        patient_id:  Optional FHIR patient ID (SHARP extension).

    Returns:
        dict with keys: subjective, objective, assessment, plan,
                        red_flags, patient_summary
    """
    context = f"[Patient ID: {patient_id}]\n" if patient_id else ""
    lang_instruction = (
        f"The input is in {language}. Understand it and output a structured "
        f"English SOAP note plus a patient summary in {language}."
        if language.lower() != "english" else ""
    )

    system = f"""You are a clinical AI assistant for rapid consultations. {lang_instruction}
Expand brief clinical notes into a full structured response. Return ONLY valid JSON:
{{
  "subjective": "Expanded chief complaint",
  "objective": "Inferred or stated vitals and findings",
  "assessment": "Most likely clinical impression",
  "plan": "Recommended management",
  "red_flags": [{{"severity": "critical|warning|watch", "title": "title", "explanation": "detail", "icon": "emoji"}}],
  "patient_summary": "Plain language summary for patient (in original language if not english)"
}}"""

    try:
        text = _call(system, context + brief_notes, max_tokens=1500)
        return _parse(text)
    except Exception as e:
        return {"error": str(e)}


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # SSE transport so Prompt Opinion can reach it over HTTP
    mcp.run(transport="streamable-http")
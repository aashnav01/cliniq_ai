"""
gemini_service.py — ClinIQ AI Service powered by Google Gemini 2.0 Flash
gemini_service.py — ClinIQ AI Service powered by Google Gemini 2.5 Flash

All clinical LLM tasks (SOAP, DDx, handover, prescription safety, ICD-10,
referral, discharge summary) use Gemini 2.5 Flash.

Voice transcription (Whisper) still uses Groq — Groq Whisper is the best-in-class
STT for medical terminology and Indian languages and there is no equivalent in the
Gemini product line at this price point.
"""

import google.generativeai as genai
from config import settings
import json
import time
import math

# Keep Groq only for Whisper STT — not for any LLM tasks
try:
    from groq import Groq as GroqClient
    _groq_available = bool(settings.groq_api_key)
except ImportError:
    GroqClient = None
    _groq_available = False


class GeminiService:
    def __init__(self):
        genai.configure(api_key=settings.gemini_api_key)
        self.model = genai.GenerativeModel("gemini-2.5-flash")
        self.model_name = "gemini-2.5-flash"

        # Groq client kept exclusively for Whisper voice transcription
        self._groq = GroqClient(api_key=settings.groq_api_key) if (_groq_available and settings.groq_api_key) else None

    # ── Core LLM call ─────────────────────────────────────────────────────────

    def _call(self, system_prompt: str, user_content: str, max_tokens: int = 2000) -> tuple[str, int]:
        """Single-turn Gemini call. Returns (text, elapsed_ms)."""
        start = time.time()
        # Gemini uses a single prompt string — we embed the system instruction
        full_prompt = f"{system_prompt}\n\n---\n\n{user_content}"
        response = self.model.generate_content(
            full_prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=0.2,   # Low temp for deterministic clinical outputs
            )
        )
        ms = int((time.time() - start) * 1000)
        return response.text, ms

    def _parse(self, text: str) -> dict:
        """Strip markdown fences and parse JSON."""
        clean = text.replace("```json", "").replace("```", "").strip()
        # Sometimes Gemini wraps in a single newline — strip again
        return json.loads(clean)

    # ── Clinical AI methods ───────────────────────────────────────────────────

    async def process_handover(self, raw_notes: str) -> dict:
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
        text, ms = self._call(system, raw_notes, 1500)
        try:
            result = self._parse(text)
        except Exception:
            result = {"error": "Failed to parse", "raw": text}
        return {"data": result, "processing_time_ms": ms, "model": self.model_name}

    async def process_soap(self, raw_notes: str) -> dict:
        system = """You are a clinical AI assistant. Convert raw consultation notes to SOAP format. Return ONLY valid JSON:
{
  "subjective": "Chief complaint and history",
  "objective": "Vital signs and exam findings",
  "assessment": "Clinical impression",
  "plan": "Management and follow-up",
  "vitals": {
    "resp_rate": null,
    "o2_sat": null,
    "any_supplemental_o2": false,
    "temperature": null,
    "systolic_bp": null,
    "heart_rate": null,
    "consciousness": "A"
  },
  "red_flags": [
    {
      "severity": "critical | warning | watch",
      "title": "Short title",
      "explanation": "Why this is a concern and what to do",
      "icon": "emoji"
    }
  ]
}
For vitals: extract numeric values where mentioned. consciousness: A=Alert, V=Voice, P=Pain, U=Unresponsive.
Sort red_flags: critical first. Return empty array if none."""
        text, ms = self._call(system, raw_notes, 2000)
        try:
            result = self._parse(text)
            vitals = result.get("vitals", {})
            result["news2"] = self._calculate_news2(vitals)
            result["qsofa"] = self._calculate_qsofa(vitals)
        except Exception:
            result = {"error": "Failed to parse", "raw": text}
        return {"data": result, "processing_time_ms": ms, "model": self.model_name}

    async def process_drug_interactions(self, plan_text: str) -> dict:
        system = """You are a clinical pharmacology AI. Extract all medications from the plan text and check for interactions.
Return ONLY valid JSON:
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
        text, ms = self._call(system, f"Check medications in this plan:\n{plan_text}", 1000)
        try:
            result = self._parse(text)
        except Exception:
            result = {"medications_found": [], "interactions": [], "notes": "Could not parse"}
        return {"data": result, "processing_time_ms": ms, "model": self.model_name}

    async def process_differential_diagnosis(self, clinical_presentation: str) -> dict:
        system = """You are a clinical AI assistant. Generate ranked differential diagnoses. Return ONLY valid JSON:
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
      "red_flag": "Specific warning or null",
      "icd10_codes": [
        {"code": "I21.9", "description": "Acute MI, unspecified", "confidence": 82}
      ]
    }
  ],
  "most_likely": "Most likely diagnosis name",
  "critical_exclusions": ["Life-threatening condition to exclude"],
  "top_icd10": [
    {"code": "I21.9", "description": "Acute MI, unspecified", "confidence": 82}
  ]
}
Rank by likelihood. Confidence 0-100. Include top 3 ICD-10 codes for the most likely diagnosis."""
        text, ms = self._call(system, clinical_presentation, 2500)
        try:
            result = self._parse(text)
        except Exception:
            result = {"error": "Failed to parse", "raw": text}
        return {"data": result, "processing_time_ms": ms, "model": self.model_name}

    async def process_referral(self, soap_data: dict, specialty: str) -> dict:
        system = f"""You are a clinical AI assistant. Write a formal referral letter to {specialty} based on the SOAP note provided.
Return ONLY valid JSON:
{{
  "letter": "Full referral letter text with proper structure: Dear Dr/Team, Reason for referral, Relevant history, Current medications, Investigations done, Urgency, Thank you closing"
}}"""
        content = f"Specialty: {specialty}\nSOAP Note:\n{json.dumps(soap_data, indent=2)}"
        text, ms = self._call(system, content, 1000)
        try:
            result = self._parse(text)
        except Exception:
            result = {"letter": text}
        return {"data": result, "processing_time_ms": ms, "model": self.model_name}

    async def process_rapid_mode(self, brief_notes: str, language: str = "english") -> dict:
        lang_instruction = ""
        if language != "english":
            lang_instruction = f"The input is in {language}. Understand it and output structured English SOAP note plus a patient summary in {language}."

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
        text, ms = self._call(system, brief_notes, 1500)
        try:
            result = self._parse(text)
        except Exception:
            result = {"error": "Failed to parse", "raw": text}
        return {"data": result, "processing_time_ms": ms, "model": self.model_name}

    async def suggest_icd10(self, clinical_text: str) -> dict:
        system = """You are a clinical coding AI. Based on the clinical text, suggest the top 3 most appropriate ICD-10-CM codes.
Return ONLY valid JSON:
{
  "suggestions": [
    {
      "code": "I21.9",
      "description": "Acute myocardial infarction, unspecified",
      "confidence": 87,
      "reasoning": "Why this code applies"
    }
  ],
  "notes": "Any coding caveats"
}"""
        text, ms = self._call(system, clinical_text, 800)
        try:
            result = self._parse(text)
        except Exception:
            result = {"suggestions": [], "notes": "Could not parse"}
        return {"data": result, "processing_time_ms": ms, "model": self.model_name}

    async def process_prescription_safety(self, drugs: list[str], patient_context: dict) -> dict:
        allergies = patient_context.get("allergies", [])
        weight    = patient_context.get("weight_kg")
        renal     = patient_context.get("renal_function", "normal")
        hepatic   = patient_context.get("hepatic_function", "normal")
        age       = patient_context.get("age")

        context_str = f"""
Patient context:
- Allergies: {', '.join(allergies) if allergies else 'None documented'}
- Weight: {weight} kg
- Renal function: {renal}
- Hepatic function: {hepatic}
- Age: {age if age else 'Not specified'}
"""
        system = """You are a clinical pharmacist AI specialising in prescription safety. Perform a comprehensive safety check.
Return ONLY valid JSON:
{
  "overall_safety": "safe | caution | dangerous",
  "flags": [
    {
      "type": "interaction | allergy | renal_dose | hepatic_dose | contraindication | weight_dose | duplicate",
      "severity": "critical | warning | watch",
      "drugs_involved": ["drug1", "drug2"],
      "title": "Short flag title",
      "detail": "Full clinical explanation",
      "recommendation": "What to do — alternative drug, dose adjustment, monitor, stop"
    }
  ],
  "safe_drugs": ["drugs with no issues"],
  "dose_adjustments": [
    {
      "drug": "drug name",
      "current": "current dose if extractable",
      "recommended": "recommended dose given patient factors",
      "reason": "why adjustment is needed"
    }
  ],
  "summary": "One paragraph plain-English summary for the prescribing doctor"
}
Be thorough. Flag: drug-drug interactions, drug-allergy conflicts, renal dose adjustments (eGFR-based),
hepatic dose adjustments, contraindications, duplicate drug classes, paediatric/weight-based dosing if relevant.
Mark anything immediately dangerous as critical."""
        drug_list    = "\n".join(f"- {d}" for d in drugs)
        user_content = f"Prescribed medications:\n{drug_list}\n{context_str}"
        text, ms = self._call(system, user_content, 2500)
        try:
            result = self._parse(text)
        except Exception:
            result = {
                "overall_safety": "caution",
                "flags": [],
                "safe_drugs": [],
                "dose_adjustments": [],
                "summary": "Could not analyse — please verify manually"
            }
        return {"data": result, "processing_time_ms": ms, "model": self.model_name}

    async def generate_discharge_summary(self, shift_data: dict) -> dict:
        """Chain all shift analyses into a GP-format discharge summary."""
        system = """You are a senior clinician AI. Generate a comprehensive discharge/handover summary in GP letter format.
Return ONLY valid JSON:
{
  "letter_date": "date string",
  "subject": "Re: Patient(s) seen during shift",
  "opening": "Dear Colleague,",
  "shift_overview": "Brief overview of the shift",
  "patients_seen": [
    {
      "name": "Patient name/identifier",
      "presenting_complaint": "Why they came",
      "assessment": "Clinical impression",
      "management": "What was done",
      "diagnoses": ["Primary", "Secondary"],
      "icd10_codes": [{"code": "X00.0", "description": "..."}],
      "prescriptions": "Medications prescribed",
      "safety_flags": ["Any critical flags"],
      "disposition": "Discharged | Admitted | Referred | Follow-up",
      "follow_up": "What the next team needs to do"
    }
  ],
  "outstanding_tasks": ["Task for incoming team"],
  "critical_alerts": ["Anything urgent the next team must know NOW"],
  "closing": "Yours sincerely, [Dr Name]",
  "news2_summary": "Highest NEWS2 scores seen this shift"
}"""
        text, ms = self._call(system, json.dumps(shift_data, indent=2, default=str), 3000)
        try:
            result = self._parse(text)
        except Exception:
            result = {"error": "Could not generate summary", "raw": text}
        return {"data": result, "processing_time_ms": ms, "model": self.model_name}

    # ── MCP Agent: Natural Language → MongoDB ─────────────────────────────────

    async def agent_query(self, natural_language_query: str, limit: int = 10) -> dict:
        """
        MongoDB MCP Agent entry point.
        Gemini translates the NL query → MongoDB filter spec → motor executes → results returned.
        """
        from mongo_service import mongo_service

        system = """You are a clinical database query agent. Convert the user's natural language
query into a MongoDB query specification.

Available collections and their key fields:
- analyses:      analysis_type (soap|handover|differential_diagnosis|rapid|prescription_safety),
                 input_text, output_data (nested JSON), processing_time_ms,
                 feedback (up|down|null), created_at, shift_id, patient_id
- patients:      name, mrn, gender, allergies (array of strings), renal_function,
                 hepatic_function, weight_kg, created_at
- shifts:        doctor_name, specialty, started_at, ended_at
- prescriptions: drugs (array), safety_result (nested), has_critical_flags (bool), created_at

Return ONLY valid JSON:
{
  "collection": "analyses",
  "filter": {},
  "sort": {"created_at": -1},
  "limit": 10,
  "summary": "Human-readable interpretation of this query",
  "insight": "What the results clinically mean"
}

Query patterns:
- Text search:      {"input_text": {"$regex": "chest pain", "$options": "i"}}
- Critical flags:   {"output_data.red_flags": {"$elemMatch": {"severity": "critical"}}}
- By type:          {"analysis_type": "soap"}
- Renal patients:   {"renal_function": {"$ne": "normal"}}
- Today's records:  {"created_at": {"$gte": "TODAY_ISO"}}
- Critical Rx:      {"has_critical_flags": true}"""

        start = time.time()
        text, ms = self._call(system, natural_language_query, 600)

        try:
            query_spec  = self._parse(text)
            collection  = query_spec.get("collection", "analyses")
            raw_filter  = query_spec.get("filter", {})
            sort        = query_spec.get("sort", {"created_at": -1})

            # Resolve TODAY_ISO placeholder
            filter_str = json.dumps(raw_filter)
            if "TODAY_ISO" in filter_str:
                from datetime import datetime, timezone
                today = datetime.now(timezone.utc).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                filter_str = filter_str.replace('"TODAY_ISO"', f'"{today.isoformat()}"')
                raw_filter = json.loads(filter_str)

            results   = await mongo_service.execute_query(collection, raw_filter, sort, min(limit, 50))
            total_ms  = int((time.time() - start) * 1000)

            return {
                "query":              natural_language_query,
                "interpreted_as":     query_spec.get("summary", ""),
                "collection_queried": collection,
                "mongo_filter":       raw_filter,
                "results":            results,
                "count":              len(results),
                "insight":            query_spec.get("insight", ""),
                "processing_time_ms": total_ms,
                "powered_by":         "Gemini 2.0 Flash + MongoDB Atlas"
            }
        except Exception as e:
            return {
                "query":   natural_language_query,
                "error":   str(e),
                "results": [],
                "count":   0,
                "powered_by": "Gemini 2.0 Flash + MongoDB Atlas"
            }

    # ── NEWS2 & qSOFA math (unchanged — pure Python) ──────────────────────────

    def _calculate_news2(self, vitals: dict) -> dict:
        score = 0
        breakdown = {}

        rr = vitals.get("resp_rate")
        if rr is not None:
            try:
                rr = float(rr)
                pts = 3 if rr <= 8 else 1 if rr <= 11 else 0 if rr <= 20 else 2 if rr <= 24 else 3
                score += pts
                breakdown["resp_rate"] = {"value": rr, "points": pts}
            except Exception:
                pass

        o2          = vitals.get("o2_sat")
        supplemental = vitals.get("any_supplemental_o2", False)
        if o2 is not None:
            try:
                o2 = float(o2)
                if supplemental:
                    pts = 3 if o2 <= 83 else 2 if o2 <= 85 else 1 if o2 <= 87 else 0 if o2 <= 92 else 2 if o2 <= 96 else 3
                else:
                    pts = 3 if o2 <= 91 else 2 if o2 <= 93 else 1 if o2 <= 95 else 0
                score += pts
                breakdown["o2_sat"] = {"value": o2, "supplemental": supplemental, "points": pts}
            except Exception:
                pass

        if supplemental:
            score += 2
            breakdown["supplemental_o2"] = {"points": 2}

        temp = vitals.get("temperature")
        if temp is not None:
            try:
                temp = float(temp)
                pts = 3 if temp <= 35.0 else 1 if temp <= 36.0 else 0 if temp <= 38.0 else 1 if temp <= 39.0 else 2
                score += pts
                breakdown["temperature"] = {"value": temp, "points": pts}
            except Exception:
                pass

        sbp = vitals.get("systolic_bp")
        if sbp is not None:
            try:
                sbp = float(sbp)
                pts = 3 if sbp <= 90 else 2 if sbp <= 100 else 1 if sbp <= 110 else 0 if sbp <= 219 else 3
                score += pts
                breakdown["systolic_bp"] = {"value": sbp, "points": pts}
            except Exception:
                pass

        hr = vitals.get("heart_rate")
        if hr is not None:
            try:
                hr = float(hr)
                pts = 3 if hr <= 40 else 1 if hr <= 50 else 0 if hr <= 90 else 1 if hr <= 110 else 2 if hr <= 130 else 3
                score += pts
                breakdown["heart_rate"] = {"value": hr, "points": pts}
            except Exception:
                pass

        consciousness = vitals.get("consciousness", "A")
        if consciousness and consciousness != "A":
            score += 3
            breakdown["consciousness"] = {"value": consciousness, "points": 3}
        else:
            breakdown["consciousness"] = {"value": "A", "points": 0}

        if score <= 4:
            severity, color = "low", "green"
            action = "Ward-based monitoring"
        elif score <= 6:
            severity, color = "medium", "amber"
            action = "Urgent review — inform senior clinician"
        else:
            severity, color = "high", "red"
            action = "EMERGENCY — immediate senior review, consider HDU/ICU"

        return {"score": score, "severity": severity, "color": color,
                "action": action, "breakdown": breakdown, "max_possible": 20}

    def _calculate_qsofa(self, vitals: dict) -> dict:
        score    = 0
        criteria = {}

        rr = vitals.get("resp_rate")
        if rr is not None:
            try:
                rr_high = float(rr) >= 22
                if rr_high:
                    score += 1
                criteria["resp_rate_22"] = {"met": rr_high, "value": float(rr)}
            except Exception:
                pass

        consciousness = vitals.get("consciousness", "A")
        altered       = bool(consciousness and consciousness != "A")
        if altered:
            score += 1
        criteria["altered_mentation"] = {"met": altered, "value": consciousness}

        sbp = vitals.get("systolic_bp")
        if sbp is not None:
            try:
                sbp_low = float(sbp) <= 100
                if sbp_low:
                    score += 1
                criteria["sbp_100"] = {"met": sbp_low, "value": float(sbp)}
            except Exception:
                pass

        return {
            "score":          score,
            "positive":       score >= 2,
            "criteria":       criteria,
            "interpretation": "Possible sepsis — investigate further" if score >= 2 else "Low sepsis risk on qSOFA"
        }

    # ── Voice Transcription (Groq Whisper — kept as-is) ───────────────────────

    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "recording.webm",
                                language: str = None) -> dict:
        """
        Transcribe clinical dictation using Groq Whisper large-v3-turbo.

        Groq Whisper is deliberately kept (not swapped to Google STT) because:
        - Best-in-class accuracy for Indian language medical dictation
        - Supports Hinglish code-switching natively
        - Significantly cheaper than Google STT at scale

        Args:
            audio_bytes: Raw audio (webm, ogg, mp3, wav, m4a)
            filename:    Used by Groq to detect audio format
            language:    ISO-639-1 hint (hi/ta/te/bn/mr) or None for auto-detect
        """
        if not self._groq:
            return {
                "data": {"text": "", "error": "GROQ_API_KEY not set — voice transcription unavailable"},
                "processing_time_ms": 0,
                "model": "whisper-large-v3-turbo"
            }

        start = time.time()
        try:
            ext  = filename.rsplit(".", 1)[-1].lower() if "." in filename else "webm"
            mime = {
                "webm": "audio/webm", "ogg": "audio/ogg",
                "mp3":  "audio/mpeg", "wav": "audio/wav",
                "m4a":  "audio/mp4",  "mp4": "audio/mp4",
            }.get(ext, "audio/webm")

            kwargs = {
                "file":            (filename, audio_bytes, mime),
                "model":           "whisper-large-v3-turbo",
                "response_format": "verbose_json",
            }
            if language:
                kwargs["language"] = language

            transcription = self._groq.audio.transcriptions.create(**kwargs)
            ms = int((time.time() - start) * 1000)
            return {
                "data": {
                    "text":     transcription.text,
                    "language": getattr(transcription, "language", language or "auto"),
                    "duration": getattr(transcription, "duration", None),
                },
                "processing_time_ms": ms,
                "model": "whisper-large-v3-turbo"
            }
        except Exception as e:
            ms = int((time.time() - start) * 1000)
            return {
                "data": {"text": "", "error": str(e)},
                "processing_time_ms": ms,
                "model": "whisper-large-v3-turbo"
            }


# Singleton
gemini_service = GeminiService()

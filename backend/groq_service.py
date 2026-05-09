from groq import Groq
from config import settings
import json
import time


class GroqService:
    def __init__(self):
        self.client = Groq(api_key=settings.groq_api_key)
        self.model = settings.groq_model

    def _call(self, system_prompt: str, user_content: str, max_tokens: int = 2000) -> tuple[str, int]:
        start = time.time()
        completion = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ]
        )
        ms = int((time.time() - start) * 1000)
        return completion.choices[0].message.content, ms

    def _parse(self, text: str) -> dict:
        clean = text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean)

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
        return {"data": result, "processing_time_ms": ms, "model": self.model}

    async def process_soap(self, raw_notes: str) -> dict:
        system = """You are a clinical AI assistant. Convert raw consultation notes to SOAP format. Return ONLY valid JSON:
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
        text, ms = self._call(system, raw_notes, 2000)
        try:
            result = self._parse(text)
        except Exception:
            result = {"error": "Failed to parse", "raw": text}
        return {"data": result, "processing_time_ms": ms, "model": self.model}

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
        return {"data": result, "processing_time_ms": ms, "model": self.model}

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
      "red_flag": "Specific warning or null"
    }
  ],
  "most_likely": "Most likely diagnosis name",
  "critical_exclusions": ["Life-threatening condition to exclude"]
}
Rank by likelihood. Confidence 0-100."""
        text, ms = self._call(system, clinical_presentation, 2500)
        try:
            result = self._parse(text)
        except Exception:
            result = {"error": "Failed to parse", "raw": text}
        return {"data": result, "processing_time_ms": ms, "model": self.model}

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
        return {"data": result, "processing_time_ms": ms, "model": self.model}

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
        return {"data": result, "processing_time_ms": ms, "model": self.model}


groq_service = GroqService()

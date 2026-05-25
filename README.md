# ClinIQ — AI-Powered Clinical Intelligence Platform

<div align="center">

![ClinIQ Banner](https://img.shields.io/badge/ClinIQ-Clinical%20AI%20Platform-3b82f6?style=for-the-badge&logo=stethoscope)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)
![Gemini](https://img.shields.io/badge/Gemini%202.0-8E75B2?style=for-the-badge&logo=google&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB-47A248?style=for-the-badge&logo=mongodb&logoColor=white)

**A full-stack AI clinical assistant that turns messy doctor dictation into structured, safe, and actionable clinical documentation — in seconds.**

[Live Demo](#) · [API Docs](http://localhost:8000/docs) · [Report Bug](#)

</div>

---

## 🧠 What is ClinIQ?

ClinIQ is a production-grade clinical intelligence platform built for doctors, medical students, and healthcare teams. It replaces hours of manual documentation with AI-powered workflows — from bedside dictation to structured SOAP notes, drug safety checks, differential diagnosis, and automated discharge summaries.

> **Built for Indian healthcare context** — supports Hinglish dictation, Indian drug brand names (Dolo, Augmentin, Pan-D), tropical disease patterns (Dengue, Malaria, TB), and regional languages.

---

## ✨ Core Features

### 🎙️ Voice Dictation → SOAP Note (The Flagship Feature)
Doctors speak naturally in **any language** — English, Hindi, Tamil, Telugu, Bengali, or Marathi. The audio is sent to **Groq's Whisper large-v3-turbo** model for transcription, then a second LLM pass structures it into a professional SOAP note with:
- **S**ubjective (chief complaint, history)
- **O**bjective (vitals, examination findings)
- **A**ssessment (clinical impression)
- **P**lan (management, follow-up)

> Dictate: *"58 saal ka mard, seene mein dard 2 din se, BP 160/95, HR 102, likely HTN crisis, start amlodipine…"*
> → Instant structured SOAP note in English + patient summary in Hindi

### 🚨 Automated Red Flag Detection
Every SOAP note is automatically scanned by the AI for clinical red flags — critical vitals, dangerous drug combinations, missed diagnoses — each ranked as **Critical / Warning / Watch** with clinical explanation and action plan.

### 📊 NEWS2 & qSOFA Scoring
Vital signs extracted from dictation are automatically scored against:
- **NEWS2** (National Early Warning Score) — colour-coded severity with recommended escalation action
- **qSOFA** — sepsis screening with positive/negative interpretation

### 💊 Drug Interaction Checker
Every plan containing medications is **automatically** cross-checked for:
- Drug-drug interactions
- Allergy conflicts (if patient profile is set)
- Renal/hepatic dose adjustments
- Duplicate drug classes

Indian brand names (Crocin, Dolo, Combiflam, Ecosprin, Pan, Augmentin, Azithral) are automatically mapped to their generic equivalents with **Jan Aushadhi** availability noted.

### 🔬 Differential Diagnosis Generator
Enter patient age, gender, symptoms, duration, vitals, and history — get a **ranked list of differential diagnoses** with:
- Confidence scores (0–100%)
- Clinical reasoning for each
- Tests to confirm / rule out
- Red flag warnings
- **ICD-10-CM billing codes** for each diagnosis

Supports **interactive symptom chips** — toggle symptoms on/off to dynamically re-run the differential.

### 📋 Shift Handover Briefing
Paste raw messy handover notes (abbreviations welcome) — AI parses all patients with:
- Urgency triage (Critical → High → Stable)
- Key events, medications, watch-for alerts
- Per-patient task checklist (Bloods, Imaging, Specialist review)
- Mark-as-reviewed workflow
- **NEWS2 manual calculator** embedded

### 💊 Prescription Safety Checker
Full pharmacovigilance AI — input a drug list + patient context (weight, allergies, renal/hepatic function, age) to get:
- **Overall safety verdict** (Safe / Caution / Dangerous)
- Per-flag explanations with recommendations
- Dose adjustment suggestions
- Safe drugs confirmed list

### 🏷️ ICD-10 Auto-Coding
Every SOAP note and differential automatically suggests the top **ICD-10-CM billing codes** with confidence percentages — streamlining hospital billing and insurance claims.

### 📄 Automated PDF Discharge Summary
At shift end, generate a **GP-format discharge letter PDF** for the entire shift — patient by patient, with diagnoses, medications, prescriptions, safety flags, and outstanding tasks. One click, ready to file.

### 📈 Analytics Dashboard
Real-time aggregated metrics across all shifts:
- Total analyses by type (SOAP, Handover, DDx, Rapid Mode)
- Average AI processing time
- Red flag frequency (critical vs warning)
- Prescription safety statistics
- Feedback (thumbs up/down) tracking

### 🔗 FHIR R4 Compliance
Full **HL7 FHIR R4** resource generation — export any patient encounter as structured FHIR JSON (Patient, Encounter, Observation, Condition, MedicationRequest, DiagnosticReport) for EHR integration.

### ⚡ Rapid Mode
For busy OPDs — dictate just 5–10 shorthand words (*"58F chest pain 2d HTN bisoprolol sats 96"*) and the AI expands it to a full SOAP note with inferred clinical reasoning.

### 🗂️ Patient Timeline
Per-patient chronological audit trail of all analyses and prescriptions — expandable detail view with full data at each time point.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 18, Vite, Vanilla CSS (no UI framework) |
| **Backend** | Python 3.11+, FastAPI |
| **AI Models** | Gemini 2.0 Flash (SOAP/DDx/Safety), Groq `whisper-large-v3-turbo` (Voice STT) |
| **Agent** | MongoDB MCP Agent (Natural language clinical querying) |
| **Database** | MongoDB Atlas (motor async driver) |
| **PDF Generation** | ReportLab |
| **FHIR** | Custom FHIR R4 resource builder |
| **Cache** | Redis (optional, graceful fallback) |
| **Deployment** | Docker |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- A free [Google Gemini API key](https://aistudio.google.com)
- A free [MongoDB Atlas Cluster URI](https://cloud.mongodb.com)
- A free [Groq API key](https://console.groq.com) (for Whisper STT)

### 1. Clone the repository
```bash
git clone https://github.com/YOUR_USERNAME/cliniq.git
cd cliniq/cliniq_fixed
```

### 2. Set up environment variables
```bash
cp .env.example .env
```
Open `.env` and configure your API keys and MongoDB URI:
```
GEMINI_API_KEY=your_gemini_key
MONGODB_URI=mongodb+srv://...
GROQ_API_KEY=your_groq_key
```

### 3. Start the Backend
```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
python main.py
```
Backend runs at → **http://localhost:8000**
Interactive API docs → **http://localhost:8000/docs**

### 4. Start the Frontend
```bash
cd frontend
npm install
npm run dev
```
Frontend runs at → **http://localhost:5173**

### 5. One-command start (Windows)
```bash
.\start-dev.bat
```

### Docker (Optional)
```bash
docker-compose up --build
```

---

## 🎙️ Testing Voice Dictation

The 🎤 **Dictate** button appears next to "Process Note" in every module.

1. Click **Dictate** (blue pill button)
2. Allow microphone access when prompted (one-time)
3. Speak your clinical notes
4. Click **Stop Recording** — button turns amber while Groq Whisper transcribes
5. Text appears in the input box — click **Process Note**

### Sample dictations to try:

**English OPD:**
> *"45 year old male, high grade fever with chills 3 days, retro-orbital pain, took Dolo at home. BP 110/70, HR 98. Suspecting Dengue. Plan NS1 antigen, CBC, Pan-D empty stomach."*

**Hinglish (select Hindi in language dropdown):**
> *"Patient ko kal raat se pet mein dard hai aur loose motions ho rahe hain. Food poisoning lagta hai. Ofloxacin aur ORS dena hai."*

**Tuberculosis DDx:**
> *"28 year old male, evening fever, 4kg weight loss in one month, chronic cough 3 weeks with blood-tinged sputum."*

---

## 📁 Project Structure

```
cliniq_fixed/
├── backend/
│   ├── main.py              # FastAPI app — all API routes
│   ├── gemini_service.py    # Gemini LLM + Whisper integration
│   ├── mongo_service.py     # MongoDB Atlas data layer
│   ├── mongodb_mcp_agent.py # Natural language MCP agent
│   ├── fhir_service.py      # FHIR R4 resource generation
│   ├── pdf_service.py       # ReportLab PDF discharge summaries
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── modules/
│       │   │   ├── SoapModule.jsx          # SOAP + Voice dictation
│       │   │   ├── HandoverModule.jsx      # Shift handover
│       │   │   ├── DifferentialDxModule.jsx # DDx generator
│       │   │   ├── PrescriptionModule.jsx  # Drug safety checker
│       │   │   ├── AnalyticsModule.jsx     # Metrics dashboard
│       │   │   ├── FhirModule.jsx          # FHIR export
│       │   │   └── TimelineModule.jsx      # Patient timeline
│       │   └── Topbar.jsx
│       ├── hooks/
│       │   └── useVoiceInput.js            # MediaRecorder → Whisper hook
│       └── index.css                       # Design system
└── docker-compose.yml
```

---

## 🔌 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/analyze/soap` | Convert raw notes to SOAP |
| `POST` | `/api/analyze/transcribe` | Voice → text (Groq Whisper) |
| `POST` | `/api/analyze/rapid` | Rapid shorthand expansion |
| `POST` | `/api/analyze/ddx` | Differential diagnosis |
| `POST` | `/api/analyze/handover` | Parse shift handover notes |
| `POST` | `/api/analyze/prescription-safety` | Drug safety check |
| `POST` | `/api/analyze/drug-interactions` | Drug interaction check |
| `POST` | `/api/analyze/icd10` | ICD-10 code suggestions |
| `POST` | `/api/analyze/referral` | Generate referral letter |
| `GET` | `/api/shift/{id}/discharge-summary` | PDF discharge summary |
| `GET` | `/api/analytics/shift` | Aggregated metrics |
| `GET` | `/api/patient/{id}/timeline` | Patient audit trail |
| `GET/POST` | `/fhir/Patient`, `/fhir/Encounter`, etc. | FHIR R4 resources |

Full interactive docs: **http://localhost:8000/docs**

---

## 🌐 Languages Supported for Voice Dictation

| Language | Code | Notes |
|---|---|---|
| English | `en` | Auto-detected, best for medical terms |
| Hindi | `hi` | Full Hinglish support |
| Tamil | `ta` | Regional Indian language |
| Telugu | `te` | Regional Indian language |
| Bengali | `bn` | Regional Indian language |
| Marathi | `mr` | Regional Indian language |

---

## 📄 License

MIT License — free to use, modify, and distribute.

---

<div align="center">
Built with ❤️ for Indian healthcare · Powered by <a href="https://aistudio.google.com">Google Gemini</a> & MongoDB Atlas
</div>

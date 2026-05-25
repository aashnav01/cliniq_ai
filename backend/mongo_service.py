"""
mongo_service.py — ClinIQ MongoDB Atlas data layer

Replaces SQLAlchemy + SQLite/PostgreSQL with MongoDB Atlas.
Uses motor (async pymongo) for full async/await FastAPI compatibility.

Collections:
  cliniq.analyses      — SOAP notes, handovers, DDx, rapid notes
  cliniq.patients      — Patient demographics and allergies
  cliniq.shifts        — Doctor shift sessions
  cliniq.prescriptions — Drug safety check results
"""

from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime
from config import settings
from typing import Optional


def _oid(id_str: str) -> ObjectId:
    """Convert string to ObjectId, raising ValueError on bad format."""
    try:
        return ObjectId(id_str)
    except Exception:
        raise ValueError(f"Invalid id: {id_str!r}")


def _serialize(doc: dict) -> dict:
    """Convert a MongoDB document to a JSON-serialisable dict.
    - _id  → id  (string)
    - datetime → ISO string
    """
    if doc is None:
        return None
    doc = dict(doc)
    if "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    # Recursively convert nested datetimes
    for k, v in doc.items():
        if isinstance(v, datetime):
            doc[k] = v.isoformat()
        elif isinstance(v, dict):
            doc[k] = _serialize(v)
    return doc


class MongoService:
    def __init__(self):
        self.client = AsyncIOMotorClient(settings.mongodb_uri)
        self.db = self.client["cliniq"]

    # Shorthand collection accessors
    @property
    def analyses(self):
        return self.db["analyses"]

    @property
    def patients(self):
        return self.db["patients"]

    @property
    def shifts(self):
        return self.db["shifts"]

    @property
    def prescriptions(self):
        return self.db["prescriptions"]

    # ── Indexes (called once at startup) ─────────────────────────────────────

    async def ensure_indexes(self):
        """Create indexes for common query patterns."""
        await self.analyses.create_index([("shift_id", 1)])
        await self.analyses.create_index([("patient_id", 1)])
        await self.analyses.create_index([("analysis_type", 1)])
        await self.analyses.create_index([("created_at", -1)])
        await self.patients.create_index([("mrn", 1)], unique=True, sparse=True)
        await self.patients.create_index([("created_at", -1)])
        await self.shifts.create_index([("started_at", -1)])
        await self.prescriptions.create_index([("shift_id", 1)])
        await self.prescriptions.create_index([("patient_id", 1)])

    # ── Analyses ──────────────────────────────────────────────────────────────

    async def save_analysis(
        self,
        analysis_type: str,
        input_text: str,
        output_data: dict,
        processing_time_ms: int,
        shift_id: Optional[str] = None,
        patient_id: Optional[str] = None,
    ) -> dict:
        doc = {
            "analysis_type":     analysis_type,
            "input_text":        input_text,
            "output_data":       output_data,
            "processing_time_ms": processing_time_ms,
            "shift_id":          shift_id,
            "patient_id":        patient_id,
            "feedback":          None,
            "created_at":        datetime.utcnow(),
        }
        result = await self.analyses.insert_one(doc)
        doc["id"] = str(result.inserted_id)
        return _serialize(doc)

    async def get_analysis(self, analysis_id: str) -> Optional[dict]:
        doc = await self.analyses.find_one({"_id": _oid(analysis_id)})
        return _serialize(doc)

    async def update_feedback(self, analysis_id: str, feedback: str) -> bool:
        r = await self.analyses.update_one(
            {"_id": _oid(analysis_id)},
            {"$set": {"feedback": feedback}}
        )
        return r.modified_count > 0

    async def get_shift_analyses(self, shift_id: str) -> list:
        cursor = self.analyses.find({"shift_id": shift_id}).sort("created_at", -1)
        return [_serialize(d) async for d in cursor]

    async def get_patient_analyses(self, patient_id: str) -> list:
        cursor = self.analyses.find({"patient_id": patient_id}).sort("created_at", 1)
        return [_serialize(d) async for d in cursor]

    async def get_analyses_by_type(self, analysis_type: str, limit: int = 20) -> list:
        cursor = self.analyses.find(
            {"analysis_type": analysis_type}
        ).sort("created_at", -1).limit(limit)
        return [_serialize(d) async for d in cursor]

    async def get_analyses_any(self, limit: int = 20) -> list:
        """Return recent analyses regardless of type — for MCP agent /recent."""
        cursor = self.analyses.find().sort("created_at", -1).limit(limit)
        return [_serialize(d) async for d in cursor]

    # ── Patients ──────────────────────────────────────────────────────────────

    async def create_patient(
        self,
        name: str,
        mrn: Optional[str] = None,
        dob: Optional[str] = None,
        gender: Optional[str] = None,
        weight_kg: Optional[float] = None,
        allergies: Optional[list] = None,
        renal_function: str = "normal",
        hepatic_function: str = "normal",
    ) -> dict:
        doc = {
            "name":             name,
            "mrn":              mrn,
            "dob":              dob,
            "gender":           gender,
            "weight_kg":        weight_kg,
            "allergies":        allergies or [],
            "renal_function":   renal_function,
            "hepatic_function": hepatic_function,
            "created_at":       datetime.utcnow(),
            "updated_at":       datetime.utcnow(),
        }
        result = await self.patients.insert_one(doc)
        doc["id"] = str(result.inserted_id)
        return _serialize(doc)

    async def get_patient(self, patient_id: str) -> Optional[dict]:
        try:
            doc = await self.patients.find_one({"_id": _oid(patient_id)})
            return _serialize(doc)
        except ValueError:
            return None

    async def list_patients(self) -> list:
        cursor = self.patients.find().sort("created_at", -1)
        return [_serialize(d) async for d in cursor]

    async def get_patient_timeline(self, patient_id: str):
        """Return (analyses_list, prescriptions_list) sorted by created_at asc."""
        a_cursor = self.analyses.find({"patient_id": patient_id}).sort("created_at", 1)
        analyses = [_serialize(d) async for d in a_cursor]

        rx_cursor = self.prescriptions.find({"patient_id": patient_id}).sort("created_at", 1)
        prescriptions = [_serialize(d) async for d in rx_cursor]

        return analyses, prescriptions

    # ── Shifts ────────────────────────────────────────────────────────────────

    async def create_shift(self, doctor_name: str, specialty: str) -> dict:
        doc = {
            "doctor_name": doctor_name,
            "specialty":   specialty,
            "started_at":  datetime.utcnow(),
            "ended_at":    None,
        }
        result = await self.shifts.insert_one(doc)
        doc["id"] = str(result.inserted_id)
        return _serialize(doc)

    async def get_shift(self, shift_id: str) -> Optional[dict]:
        try:
            doc = await self.shifts.find_one({"_id": _oid(shift_id)})
            return _serialize(doc)
        except ValueError:
            return None

    async def end_shift(self, shift_id: str) -> Optional[dict]:
        await self.shifts.update_one(
            {"_id": _oid(shift_id)},
            {"$set": {"ended_at": datetime.utcnow()}}
        )
        return await self.get_shift(shift_id)

    async def get_shift_prescriptions(self, shift_id: str) -> list:
        cursor = self.prescriptions.find({"shift_id": shift_id}).sort("created_at", -1)
        return [_serialize(d) async for d in cursor]

    # ── Prescriptions ─────────────────────────────────────────────────────────

    async def save_prescription(
        self,
        shift_id: Optional[str],
        patient_id: Optional[str],
        drugs: list,
        patient_context: dict,
        safety_result: dict,
        has_critical_flags: bool,
    ) -> dict:
        doc = {
            "shift_id":           shift_id,
            "patient_id":         patient_id,
            "drugs":              drugs,
            "patient_context":    patient_context,
            "safety_result":      safety_result,
            "has_critical_flags": has_critical_flags,
            "created_at":         datetime.utcnow(),
        }
        result = await self.prescriptions.insert_one(doc)
        doc["id"] = str(result.inserted_id)
        return _serialize(doc)

    async def get_patient_prescriptions(self, patient_id: str) -> list:
        cursor = self.prescriptions.find({"patient_id": patient_id}).sort("created_at", 1)
        return [_serialize(d) async for d in cursor]

    # ── Analytics ─────────────────────────────────────────────────────────────

    async def get_all_analytics(self) -> dict:
        all_analyses     = await self.analyses.find().to_list(length=None)
        all_shifts       = await self.shifts.find().to_list(length=None)
        all_prescriptions = await self.prescriptions.find().to_list(length=None)

        by_type: dict = {}
        for a in all_analyses:
            t = a.get("analysis_type", "unknown")
            if t not in by_type:
                by_type[t] = {"count": 0, "total_ms": 0, "feedback_up": 0, "feedback_down": 0}
            by_type[t]["count"]    += 1
            by_type[t]["total_ms"] += a.get("processing_time_ms", 0) or 0
            if a.get("feedback") == "up":   by_type[t]["feedback_up"]   += 1
            if a.get("feedback") == "down": by_type[t]["feedback_down"] += 1

        for t in by_type:
            c = by_type[t]["count"]
            by_type[t]["avg_ms"] = int(by_type[t]["total_ms"] / c) if c else 0

        red_flag_count = critical_count = 0
        for a in all_analyses:
            flags = (a.get("output_data") or {}).get("red_flags", [])
            red_flag_count += len(flags)
            critical_count += sum(1 for f in flags if f.get("severity") == "critical")

        total_rx    = len(all_prescriptions)
        critical_rx = sum(1 for p in all_prescriptions if p.get("has_critical_flags"))
        n           = len(all_analyses)

        return {
            "total_analyses":        n,
            "total_shifts":          len(all_shifts),
            "total_prescriptions":   total_rx,
            "critical_prescriptions": critical_rx,
            "by_type":               by_type,
            "red_flags":             {"total": red_flag_count, "critical": critical_count},
            "avg_processing_ms":     int(
                sum(a.get("processing_time_ms", 0) or 0 for a in all_analyses) / n
            ) if n else 0,
        }

    # ── Raw query (MCP Agent) ─────────────────────────────────────────────────

    async def execute_query(
        self,
        collection: str,
        filter: dict,
        sort: dict,
        limit: int = 10,
    ) -> list:
        """
        Execute an arbitrary MongoDB query against any clinical collection.
        Called by the Gemini MCP Agent to answer natural language queries.
        """
        allowed = {"analyses", "patients", "shifts", "prescriptions"}
        if collection not in allowed:
            raise ValueError(f"Collection '{collection}' is not allowed. Choose from: {allowed}")

        coll      = self.db[collection]
        sort_list = list(sort.items()) if sort else [("created_at", -1)]

        cursor = coll.find(filter).sort(sort_list).limit(min(limit, 50))
        return [_serialize(d) async for d in cursor]


# Singleton
mongo_service = MongoService()

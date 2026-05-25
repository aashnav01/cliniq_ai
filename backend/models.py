from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


class ShiftSession(Base):
    __tablename__ = "shift_sessions"

    id = Column(Integer, primary_key=True, index=True)
    doctor_name = Column(String, default="Doctor")
    specialty = Column(String, default="")
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)

    analyses = relationship("Analysis", back_populates="shift", cascade="all, delete-orphan")
    prescriptions = relationship("Prescription", back_populates="shift", cascade="all, delete-orphan")


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    mrn = Column(String, nullable=True, unique=True, index=True)   # Medical Record Number
    dob = Column(String, nullable=True)                             # YYYY-MM-DD
    gender = Column(String, nullable=True)
    weight_kg = Column(Float, nullable=True)
    allergies = Column(JSON, default=list)                          # ["penicillin", "sulfa"]
    renal_function = Column(String, nullable=True)                  # normal | mild | moderate | severe | dialysis
    hepatic_function = Column(String, nullable=True)                # normal | mild | moderate | severe
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    analyses = relationship("Analysis", back_populates="patient", cascade="all, delete-orphan")
    prescriptions = relationship("Prescription", back_populates="patient", cascade="all, delete-orphan")


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, index=True)
    shift_id = Column(Integer, ForeignKey("shift_sessions.id"), nullable=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=True)
    input_text = Column(Text)
    output_data = Column(JSON)
    analysis_type = Column(String)   # handover | soap | differential_diagnosis | rapid | prescription_safety
    processing_time_ms = Column(Integer)
    feedback = Column(String, nullable=True)   # up | down | None
    created_at = Column(DateTime, default=datetime.utcnow)

    shift = relationship("ShiftSession", back_populates="analyses")
    patient = relationship("Patient", back_populates="analyses")


class Prescription(Base):
    __tablename__ = "prescriptions"

    id = Column(Integer, primary_key=True, index=True)
    shift_id = Column(Integer, ForeignKey("shift_sessions.id"), nullable=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=True)
    drugs = Column(JSON)              # ["warfarin 5mg od", "aspirin 75mg od"]
    patient_context = Column(JSON)    # weight, allergies, renal/hepatic at time of check
    safety_result = Column(JSON)      # full AI safety analysis
    has_critical_flags = Column(Integer, default=0)   # 0 | 1 — quick filter
    created_at = Column(DateTime, default=datetime.utcnow)

    shift = relationship("ShiftSession", back_populates="prescriptions")
    patient = relationship("Patient", back_populates="prescriptions")

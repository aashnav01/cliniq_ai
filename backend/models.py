from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON
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


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, index=True)
    shift_id = Column(Integer, ForeignKey("shift_sessions.id"), nullable=True)
    input_text = Column(Text)
    output_data = Column(JSON)
    analysis_type = Column(String)  # handover | soap | differential_diagnosis
    processing_time_ms = Column(Integer)
    feedback = Column(String, nullable=True)  # up | down | None
    created_at = Column(DateTime, default=datetime.utcnow)

    shift = relationship("ShiftSession", back_populates="analyses")

"""SQLite persistence using SQLAlchemy (ORM declarative style)."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker

_DEFAULT_DB = Path(__file__).parent.parent / "data" / "sessions.db"


class Base(DeclarativeBase):
    pass


class Presentation(Base):
    __tablename__ = "presentations"

    id = Column(Integer, primary_key=True)
    title = Column(String(256), nullable=False)
    text = Column(Text, nullable=False)
    reference_audio = Column(String(512))
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    segments = relationship("Segment", back_populates="presentation", cascade="all, delete-orphan")
    sessions = relationship("TrainingSession", back_populates="presentation", cascade="all, delete-orphan")


class Segment(Base):
    __tablename__ = "segments"

    id = Column(Integer, primary_key=True)
    presentation_id = Column(Integer, ForeignKey("presentations.id"), nullable=False)
    segment_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    attempts = Column(Integer, default=0)
    total_errors = Column(Integer, default=0)
    total_hesitations = Column(Integer, default=0)

    presentation = relationship("Presentation", back_populates="segments")

    @property
    def difficulty_score(self) -> float:
        if not self.attempts:
            return 1.0
        return (self.total_errors + self.total_hesitations) / self.attempts


class TrainingSession(Base):
    __tablename__ = "training_sessions"

    id = Column(Integer, primary_key=True)
    presentation_id = Column(Integer, ForeignKey("presentations.id"), nullable=False)
    level = Column(Integer, nullable=False)
    started_at = Column(DateTime, default=lambda: datetime.now(UTC))
    completed_at = Column(DateTime)
    mean_score = Column(Float)

    presentation = relationship("Presentation", back_populates="sessions")
    attempts = relationship("Attempt", back_populates="session", cascade="all, delete-orphan")


class Attempt(Base):
    __tablename__ = "attempts"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("training_sessions.id"), nullable=False)
    segment_index = Column(Integer, nullable=False)
    attempt_text = Column(Text)
    error_count = Column(Integer, default=0)
    hesitation_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    session = relationship("TrainingSession", back_populates="attempts")


def get_engine(db_path: str | Path = _DEFAULT_DB):
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(engine)
    return engine


def make_session_factory(db_path: str | Path = _DEFAULT_DB) -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(db_path), expire_on_commit=False)

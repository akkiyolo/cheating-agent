from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, utcnow
from app.models.types import JSONType, new_id


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    duration_s: Mapped[int] = mapped_column(Integer)
    # {"mcq": 10, "numerical": 3, ...}: how many instances of each kind to draw per session
    composition: Mapped[dict[str, Any]] = mapped_column(JSONType)
    shuffle_questions: Mapped[bool] = mapped_column(default=True)
    shuffle_options: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Question(Base):
    """A question *template* in the bank. Instances are generated per session with fresh parameters."""

    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)  # template key
    kind: Mapped[str] = mapped_column(String(20), index=True)
    topic: Mapped[str] = mapped_column(String(60))
    difficulty: Mapped[int] = mapped_column(Integer, default=2)
    parametric: Mapped[bool] = mapped_column(default=False)


class AssessmentQuestion(Base):
    """Which templates are eligible for an assessment (the draw pool)."""

    __tablename__ = "assessment_questions"
    __table_args__ = (UniqueConstraint("assessment_id", "question_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"))
    weight: Mapped[float] = mapped_column(Float, default=1.0)


class AssessmentSession(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    seed: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="in_progress")  # in_progress|submitted|expired
    started_at: Mapped[datetime] = mapped_column(default=utcnow)
    deadline: Mapped[datetime]
    submitted_at: Mapped[datetime | None] = mapped_column(default=None)
    # Generated question instances incl. answer keys. Never sent to the client as-is.
    question_set: Mapped[list[Any]] = mapped_column(JSONType)
    review_marks: Mapped[list[Any]] = mapped_column(JSONType, default=list)
    faults: Mapped[list[Any]] = mapped_column(JSONType, default=list)
    fault_state: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    score: Mapped[float | None] = mapped_column(Float, default=None)
    max_score: Mapped[float | None] = mapped_column(Float, default=None)
    result_detail: Mapped[dict[str, Any] | None] = mapped_column(JSONType, default=None)


class Answer(Base):
    __tablename__ = "answers"
    __table_args__ = (UniqueConstraint("session_id", "question_uid"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    question_uid: Mapped[str] = mapped_column(String(40))
    response: Mapped[dict[str, Any]] = mapped_column(JSONType)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
    correct: Mapped[bool | None] = mapped_column(default=None)
    points: Mapped[float | None] = mapped_column(Float, default=None)

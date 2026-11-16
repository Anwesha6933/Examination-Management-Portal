from datetime import date, datetime, time
from typing import Optional

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Table, Text, Time
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)

# ---- vocabulary used by routes and templates ----
ADMIN, EXAMINER, STUDENT = "admin", "examiner", "student"

EX_PENDING, EX_APPROVED, EX_REJECTED, EX_DEACTIVATED = "Pending", "Approved", "Rejected", "Deactivated"
ACTIVE, INACTIVE = "Active", "Inactive"
EXAM_TYPES = ["Viva", "Practical", "Project Demo", "Assessment"]
DRAFT, SLOT_CREATION, BOOKING_OPEN, CLOSED, COMPLETED = "Draft", "Slot Creation", "Booking Open", "Closed", "Completed"
AVAILABLE, FULL, CANCELLED, DONE = "Available", "Full", "Cancelled", "Completed"
BOOKED, B_CANCELLED, B_DONE = "Booked", "Cancelled", "Completed"


class User(db.Model, UserMixin):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(120), unique=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)

    examiner: Mapped[Optional["Examiner"]] = relationship(back_populates="user")
    student: Mapped[Optional["Student"]] = relationship(back_populates="user")


class Examiner(db.Model):
    __tablename__ = "examiner_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), unique=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    department: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default=EX_PENDING)

    user: Mapped["User"] = relationship(back_populates="examiner")
    slots: Mapped[list["ExamSlot"]] = relationship(back_populates="examiner")
    exams: Mapped[list["Exam"]] = relationship(secondary="exam_examiners", back_populates="examiners")


class Student(db.Model):
    __tablename__ = "student_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), unique=True)
    roll_number: Mapped[str] = mapped_column(String(30), unique=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20))

    user: Mapped["User"] = relationship(back_populates="student")
    bookings: Mapped[list["Booking"]] = relationship(back_populates="student")


class Course(db.Model):
    __tablename__ = "course_catalog"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default=ACTIVE)

    exams: Mapped[list["Exam"]] = relationship(back_populates="course")


# plain association table: which examiners may run which exam
exam_examiners = Table(
    "exam_examiners",
    Base.metadata,
    Column("exam_id", Integer, ForeignKey("examinations.id"), primary_key=True),
    Column("examiner_id", Integer, ForeignKey("examiner_profiles.id"), primary_key=True),
)


class Exam(db.Model):
    __tablename__ = "examinations"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("course_catalog.id"))
    name: Mapped[str] = mapped_column(String(100))
    exam_type: Mapped[str] = mapped_column(String(30))
    duration_minutes: Mapped[int]
    max_marks: Mapped[int]
    slot_creation_start: Mapped[date]
    slot_creation_end: Mapped[date]
    booking_start: Mapped[date]
    booking_end: Mapped[date]
    status: Mapped[str] = mapped_column(String(20), default=DRAFT)

    course: Mapped["Course"] = relationship(back_populates="exams")
    examiners: Mapped[list["Examiner"]] = relationship(secondary=exam_examiners, back_populates="exams")
    rubrics: Mapped[list["Rubric"]] = relationship(back_populates="exam", order_by="Rubric.id")
    slots: Mapped[list["ExamSlot"]] = relationship(back_populates="exam", order_by="ExamSlot.date")


class Rubric(db.Model):
    __tablename__ = "rubric_criteria"

    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("examinations.id"))
    criterion_name: Mapped[str] = mapped_column(String(100))
    max_marks: Mapped[int]
    weightage: Mapped[int]
    description: Mapped[Optional[str]] = mapped_column(Text)

    exam: Mapped["Exam"] = relationship(back_populates="rubrics")
    scores: Mapped[list["Score"]] = relationship(back_populates="rubric")


class ExamSlot(db.Model):
    __tablename__ = "exam_slots"

    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("examinations.id"))
    examiner_id: Mapped[int] = mapped_column(ForeignKey("examiner_profiles.id"))
    date: Mapped[date]
    start_time: Mapped[time]
    end_time: Mapped[time]
    capacity: Mapped[int]
    available_seats: Mapped[int]
    status: Mapped[str] = mapped_column(String(20), default=AVAILABLE)

    exam: Mapped["Exam"] = relationship(back_populates="slots")
    examiner: Mapped["Examiner"] = relationship(back_populates="slots")
    bookings: Mapped[list["Booking"]] = relationship(back_populates="slot")


class Booking(db.Model):
    __tablename__ = "slot_bookings"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.id"))
    slot_id: Mapped[int] = mapped_column(ForeignKey("exam_slots.id"))
    booked_at: Mapped[datetime] = mapped_column(default=datetime.now)
    status: Mapped[str] = mapped_column(String(20), default=BOOKED)

    student: Mapped["Student"] = relationship(back_populates="bookings")
    slot: Mapped["ExamSlot"] = relationship(back_populates="bookings")
    evaluation: Mapped[Optional["Evaluation"]] = relationship(back_populates="booking")


class Evaluation(db.Model):
    __tablename__ = "evaluations"

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("slot_bookings.id"), unique=True)
    examiner_id: Mapped[int] = mapped_column(ForeignKey("examiner_profiles.id"))
    total_marks: Mapped[int]
    remarks: Mapped[str] = mapped_column(Text)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    evaluated_at: Mapped[datetime] = mapped_column(default=datetime.now)

    booking: Mapped["Booking"] = relationship(back_populates="evaluation")
    examiner: Mapped["Examiner"] = relationship()
    scores: Mapped[list["Score"]] = relationship(back_populates="evaluation")


class Score(db.Model):
    __tablename__ = "rubric_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    evaluation_id: Mapped[int] = mapped_column(ForeignKey("evaluations.id"))
    rubric_id: Mapped[int] = mapped_column(ForeignKey("rubric_criteria.id"))
    marks: Mapped[int]

    evaluation: Mapped["Evaluation"] = relationship(back_populates="scores")
    rubric: Mapped["Rubric"] = relationship(back_populates="scores")
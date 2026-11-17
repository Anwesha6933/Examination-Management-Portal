from datetime import datetime, date, time
from typing import Optional, List

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import String, Text, ForeignKey, Column
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)


exam_examiners = db.Table(
    "exam_examiners",
    Column("exam_id", ForeignKey("examinations.id"), primary_key=True),
    Column("examiner_id", ForeignKey("examiner_profiles.id"), primary_key=True),
)
class User(UserMixin, db.Model):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(120), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))          # admin / examiner / student
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)

    examiner: Mapped[Optional["Examiner"]] = relationship(back_populates="user", uselist=False)
    student: Mapped[Optional["Student"]] = relationship(back_populates="user", uselist=False)


class Examiner(db.Model):
    __tablename__ = "examiner_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), unique=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    department: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="Pending")  # Pending / Approved / Rejected / Deactivated

    user: Mapped["User"] = relationship(back_populates="examiner")
    exams: Mapped[List["Exam"]] = relationship(secondary=exam_examiners, back_populates="examiners")
    slots: Mapped[List["ExamSlot"]] = relationship(back_populates="examiner")


class Student(db.Model):
    __tablename__ = "student_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), unique=True)
    roll_number: Mapped[str] = mapped_column(String(20), unique=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20))

    user: Mapped["User"] = relationship(back_populates="student")
    bookings: Mapped[List["Booking"]] = relationship(back_populates="student")
class Course(db.Model):
    __tablename__ = "course_catalog"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), default="Active")   # Active / Inactive

    exams: Mapped[List["Exam"]] = relationship(back_populates="course")


class Exam(db.Model):
    __tablename__ = "examinations"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("course_catalog.id"))
    title: Mapped[str] = mapped_column(String(150))
    exam_type: Mapped[str] = mapped_column(String(50))
    duration_minutes: Mapped[int]
    max_marks: Mapped[int]
    slot_creation_start: Mapped[Optional[date]]
    slot_creation_end: Mapped[Optional[date]]
    booking_start: Mapped[Optional[date]]
    booking_end: Mapped[Optional[date]]
    status: Mapped[str] = mapped_column(String(20), default="Draft")
    

    course: Mapped["Course"] = relationship(back_populates="exams")
    examiners: Mapped[List["Examiner"]] = relationship(secondary=exam_examiners, back_populates="exams")
    rubric: Mapped[List["Rubric"]] = relationship(back_populates="exam", cascade="all, delete-orphan")
    slots: Mapped[List["ExamSlot"]] = relationship(back_populates="exam")


class Rubric(db.Model):
    __tablename__ = "rubric_criteria"

    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("examinations.id"))
    name: Mapped[str] = mapped_column(String(100))
    max_marks: Mapped[float]
    weightage: Mapped[float] = mapped_column(default=0)

    exam: Mapped["Exam"] = relationship(back_populates="rubric")
class ExamSlot(db.Model):
    __tablename__ = "exam_slots"

    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("examinations.id"))
    examiner_id: Mapped[int] = mapped_column(ForeignKey("examiner_profiles.id"))
    slot_date: Mapped[date]
    start_time: Mapped[time]
    end_time: Mapped[time]
    capacity: Mapped[int] = mapped_column(default=1)
    available_seats: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(String(20), default="Available")  # Available / Full / Cancelled

    exam: Mapped["Exam"] = relationship(back_populates="slots")
    examiner: Mapped["Examiner"] = relationship(back_populates="slots")
    bookings: Mapped[List["Booking"]] = relationship(back_populates="slot")


class Booking(db.Model):
    __tablename__ = "slot_bookings"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.id"))
    slot_id: Mapped[int] = mapped_column(ForeignKey("exam_slots.id"))
    status: Mapped[str] = mapped_column(String(20), default="Booked")     # Booked / Cancelled
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)

    student: Mapped["Student"] = relationship(back_populates="bookings")
    slot: Mapped["ExamSlot"] = relationship(back_populates="bookings")
    evaluation: Mapped[Optional["Evaluation"]] = relationship(back_populates="booking", uselist=False)


class Evaluation(db.Model):
    __tablename__ = "evaluations"

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("slot_bookings.id"), unique=True)
    total_marks: Mapped[float] = mapped_column(default=0)
    remarks: Mapped[Optional[str]] = mapped_column(Text)
    is_published: Mapped[bool] = mapped_column(default=False)
    evaluated_at: Mapped[datetime] = mapped_column(default=datetime.now)

    booking: Mapped["Booking"] = relationship(back_populates="evaluation")
    scores: Mapped[List["Score"]] = relationship(back_populates="evaluation", cascade="all, delete-orphan")


class Score(db.Model):
    __tablename__ = "rubric_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    evaluation_id: Mapped[int] = mapped_column(ForeignKey("evaluations.id"))
    rubric_id: Mapped[int] = mapped_column(ForeignKey("rubric_criteria.id"))
    marks: Mapped[float]
    remarks: Mapped[Optional[str]] = mapped_column(String(255))

    evaluation: Mapped["Evaluation"] = relationship(back_populates="scores")
    rubric: Mapped["Rubric"] = relationship()
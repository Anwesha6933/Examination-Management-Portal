"""Demo data. Run from the project root:   python -m backend.sample_data
WARNING: this wipes the database first. Dates are relative to today."""
from datetime import date, datetime, time, timedelta

from werkzeug.security import generate_password_hash

from app import app
from backend.helpers import recount_seats
from backend.models import (Booking, Course, Evaluation, Exam, ExamSlot, Examiner,
                            Rubric, Score, Student, User, db)
from backend.seed import seed_admin

PASSWORD = "pass123"

VIVA_RUBRIC = [("Concept clarity", 40, 40), ("Problem solving", 40, 40), ("Communication", 20, 20)]
DEMO_RUBRIC = [("Implementation", 50, 50), ("Presentation", 30, 30), ("Questions and answers", 20, 20)]
ORAL_RUBRIC = [("Accuracy", 25, 50), ("Reasoning", 15, 30), ("Presentation", 10, 20)]


def add_examiner(name, email, department, status, pw_hash, phone):
    user = User(name=name, email=email, role="examiner", password_hash=pw_hash)
    db.session.add(user)
    db.session.flush()
    examiner = Examiner(user_id=user.id, department=department, phone=phone, status=status)
    db.session.add(examiner)
    db.session.flush()
    return examiner


def add_student(name, email, roll, pw_hash, phone):
    user = User(name=name, email=email, role="student", password_hash=pw_hash)
    db.session.add(user)
    db.session.flush()
    student = Student(user_id=user.id, roll_number=roll, phone=phone)
    db.session.add(student)
    db.session.flush()
    return student


def add_course(code, name, description, status="Active"):
    course = Course(code=code, name=name, description=description, status=status)
    db.session.add(course)
    db.session.flush()
    return course


def add_exam(course, title, exam_type, minutes, marks, creation, booking, status, examiners, criteria):
    exam = Exam(course_id=course.id, title=title, exam_type=exam_type,
                duration_minutes=minutes, max_marks=marks,
                slot_creation_start=creation[0], slot_creation_end=creation[1],
                booking_start=booking[0], booking_end=booking[1], status=status)
    exam.examiners = examiners
    for name, max_marks, weight in criteria:
        exam.rubric.append(Rubric(name=name, max_marks=max_marks, weightage=weight))
    db.session.add(exam)
    db.session.flush()
    return exam


def add_slot(exam, examiner, day, hour, minute, capacity):
    start = time(hour, minute)
    end = (datetime.combine(day, start) + timedelta(minutes=exam.duration_minutes)).time()
    slot = ExamSlot(exam_id=exam.id, examiner_id=examiner.id, slot_date=day,
                    start_time=start, end_time=end, capacity=capacity,
                    available_seats=capacity, status="Available")
    db.session.add(slot)
    db.session.flush()
    return slot


def add_booking(student, slot, days_ago, status="Booked"):
    booking = Booking(student_id=student.id, slot_id=slot.id, status=status,
                      created_at=datetime.now() - timedelta(days=days_ago))
    db.session.add(booking)
    db.session.flush()
    return booking


def grade(booking, scores, overall, published):
    """scores: one (marks, remark) pair per rubric criterion, in rubric order."""
    exam = booking.slot.exam
    ev = Evaluation(booking_id=booking.id, remarks=overall, is_published=published,
                    evaluated_at=datetime.combine(booking.slot.slot_date, time(17, 0)))
    total = 0
    for rubric, (marks, note) in zip(exam.rubric, scores):
        ev.scores.append(Score(rubric_id=rubric.id, marks=marks, remarks=note))
        total += marks
    ev.total_marks = total
    db.session.add(ev)
    db.session.flush()


def load():
    db.drop_all()
    db.create_all()
    seed_admin()

    today = date.today()
    d = lambda n: today + timedelta(days=n)
    pw = generate_password_hash(PASSWORD)

    # ---- people ----
    anil = add_examiner("Dr. Anil Rao", "anil@emp.com", "Computer Science", "Approved", pw, "9876500001")
    meera = add_examiner("Prof. Meera Nair", "meera@emp.com", "Computer Science", "Approved", pw, "9876500002")
    kiran = add_examiner("Dr. Kiran Shah", "kiran@emp.com", "Mathematics", "Approved", pw, "9876500003")
    add_examiner("Dr. Vikram Sethi", "vikram@emp.com", "Electronics", "Pending", pw, None)
    add_examiner("Prof. Pooja Iyer", "pooja@emp.com", "Physics", "Deactivated", pw, None)

    rahul = add_student("Rahul Verma", "rahul@emp.com", "21F1000101", pw, "9000000101")
    sneha = add_student("Sneha Pillai", "sneha@emp.com", "21F1000102", pw, None)
    karan = add_student("Karan Malhotra", "karan@emp.com", "21F1000103", pw, None)
    divya = add_student("Divya Menon", "divya@emp.com", "21F1000104", pw, "9000000104")
    priya = add_student("Priya Das", "priya@emp.com", "21F1000105", pw, None)
    add_student("Arjun Bose", "arjun@emp.com", "21F1000106", pw, None)

    # ---- courses ----
    cs101 = add_course("CS101", "Programming Fundamentals", "Basics of programming and problem solving.")
    cs201 = add_course("CS201", "Database Systems", "Relational design and SQL.")
    ma101 = add_course("MA101", "Calculus", "Limits, derivatives and integrals.")
    ph101 = add_course("PH101", "Engineering Physics", "Mechanics and waves.")
    add_course("EC101", "Basic Electronics", "Circuits and devices.", status="Inactive")

    # ---- 1. finished exam, results published ----
    done = add_exam(cs101, "Programming Viva - Mid Term", "Viva", 20, 100,
                    (d(-75), d(-65)), (d(-64), d(-55)), "Completed", [anil], VIVA_RUBRIC)
    done_slot = add_slot(done, anil, d(-45), 10, 0, 2)
    b1 = add_booking(rahul, done_slot, 60)
    b2 = add_booking(sneha, done_slot, 60)
    grade(b1, [(34, "Clear on loops and arrays"), (32, None), (16, "Spoke confidently")],
          "Good attempt overall.", True)
    grade(b2, [(37, None), (36, "Solved the extension question"), (18, None)],
          "Excellent work.", True)

    # ---- 2. closed exam: one evaluated (unpublished), one waiting ----
    closed = add_exam(cs101, "Programming Viva - End Term", "Viva", 20, 100,
                      (d(-30), d(-22)), (d(-21), d(-12)), "Closed", [meera], VIVA_RUBRIC)
    closed_slot = add_slot(closed, meera, d(-5), 11, 0, 2)
    b3 = add_booking(rahul, closed_slot, 18)
    add_booking(priya, closed_slot, 18)
    grade(b3, [(30, None), (30, "Missed an edge case"), (16, None)],
          "Solid, slight dip in problem solving.", False)

    # ---- 3. exam open for booking ----
    open_exam = add_exam(cs201, "Database Project Demo", "Project Demo", 30, 100,
                         (d(-12), d(-4)), (d(-3), d(10)), "Booking Open", [anil, meera], DEMO_RUBRIC)
    anil_slot = add_slot(open_exam, anil, d(14), 10, 0, 2)
    meera_slot = add_slot(open_exam, meera, d(14), 14, 0, 2)
    add_booking(karan, anil_slot, 2)
    add_booking(divya, meera_slot, 1)
    add_booking(sneha, anil_slot, 2, status="Cancelled")

    # ---- 4. exam in slot creation (Kiran can add slots now) ----
    add_exam(ma101, "Calculus Oral Exam", "Oral", 15, 50,
             (d(-3), d(7)), (d(8), d(15)), "Slot Creation", [kiran], ORAL_RUBRIC)

    # ---- 5. draft exam (only the admin sees it) ----
    add_exam(ph101, "Physics Practical", "Practical", 45, 100,
             (d(10), d(20)), (d(21), d(30)), "Draft", [], [("Setup and procedure", 30, 30)])

    for slot in ExamSlot.query.all():
        recount_seats(slot)
    db.session.commit()

    print("Demo data loaded. Password for every demo account:", PASSWORD)
    print("Admin: admin@emp.com / admin123")
    print("Examiners: anil, meera, kiran, vikram (pending), pooja (deactivated)  @emp.com")
    print("Students: rahul, sneha, karan, divya, priya, arjun  @emp.com")


if __name__ == "__main__":
    answer = input("This wipes the database and loads demo data. Type yes to continue: ")
    if answer.strip().lower() != "yes":
        print("Cancelled.")
    else:
        with app.app_context():
            load()
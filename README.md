# Examly: Examination Management Portal (MAD-1)
Name: Anwesha Dash | Roll number: 25f2006933 | MAD-1 project

A Flask web app with three roles. The **admin** sets up courses, examinations and rubrics and controls the time windows. **Examiners** open slots and grade students against the rubric. **Students** book one slot per exam and see their marks once the admin publishes them. The look: indigo colours, a top navigation bar and coloured count tiles.

Stack: Flask, Flask-SQLAlchemy (SQLite), Flask-Login, Jinja2, HTML, CSS, Bootstrap 5. No JavaScript.

## Run it

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py                     # then open http://127.0.0.1:5000
```

The database (`backend/examly.sqlite3`) and the admin account are created the first time the app starts.

Examiners and students register at `/register`. An examiner has to be approved by the admin before logging in.

## Demo accounts

The admin account always exists. All the other accounts below appear only after you load the demo data:

```bash
python -m backend.sample_data      # wipes the database and loads demo rows; exam dates are relative to today
```

| Role | Name | Email | Password | What you will see |
| --- | --- | --- | --- | --- |
| Admin | Administrator | `admin@emp.com` | `admin123` | everything; created automatically, even without demo data |
| Examiner (approved) | Dr. Anil Rao, Computer Science | `anil@emp.com` | `pass123` | finished exam with published results; a slot in the exam that is open for booking |
| Examiner (approved) | Prof. Meera Nair, Computer Science | `meera@emp.com` | `pass123` | a slot in the exam that is open for booking; closed exam with one student still to evaluate |
| Examiner (approved) | Dr. Kiran Shah, Mathematics | `kiran@emp.com` | `pass123` | the exam in slot creation (can add slots now) |
| Examiner (pending) | Dr. Vikram Sethi, Electronics | `vikram@emp.com` | `pass123` | login shows the waiting-for-approval page; approve from Admin > Examiners |
| Examiner (deactivated) | Prof. Pooja Iyer, Physics | `pooja@emp.com` | `pass123` | login is refused |
| Student | Rahul Verma (21F1000101) | `rahul@emp.com` | `pass123` | published result; evaluated (unpublished) in the closed exam |
| Student | Sneha Pillai (21F1000102) | `sneha@emp.com` | `pass123` | published result; a cancelled booking in history |
| Student | Karan Malhotra (21F1000103) | `karan@emp.com` | `pass123` | booked in the exam that is open for booking |
| Student | Divya Menon (21F1000104) | `divya@emp.com` | `pass123` | booked in the exam that is open for booking |
| Student | Priya Das (21F1000105) | `priya@emp.com` | `pass123` | booked in the closed exam, waiting for evaluation |
| Student | Arjun Bose (21F1000106) | `arjun@emp.com` | `pass123` | no bookings yet (can book the open exam) |

The demo data also contains a draft exam (only the admin sees it) and an exam in the slot-creation stage.

## Feature check against the problem statement

Every row below was tested automatically on this project (111 checks in total) and passed on 7 Nov 2026.

| Requirement (from the problem statement) | Status |
| --- | --- |
| Admin exists in the database and cannot register | Done |
| Examiner registers, waits for approval (`/pending`); admin approves, rejects or deactivates | Done |
| Student registers and logs in straight away; edits profile | Done |
| Admin: create, edit and delete courses, examinations and rubric criteria | Done |
| Admin: add examiners directly, assign examiners to an exam | Done |
| Admin: set exam dates; open and close slot creation and booking; publish results | Done |
| Admin: view all slots, bookings, students, examiners and exams, including past ones | Done |
| Admin: reschedule a booking, change a slot's examiner, cancel an empty slot | Done |
| Admin: search students, examiners, exams and bookings by name or ID | Done |
| Admin dashboard: totals of courses, exams, examiners, students, slots, bookings, plus bookings per exam | Done |
| Examiner: assigned exams; create slots only in the window; edit/remove only before booking opens | Done |
| Examiner: see booked students; grade each rubric criterion with remarks | Done |
| Examiner dashboard: assigned exams, slots created, students booked, evaluations pending | Done |
| Student: search and filter exams, exam details, book with a confirmation step | Done |
| Student: cancel only before the booking end date | Done |
| Student: booking status, full history, upcoming exams, published results with remarks, CSV scorecard | Done |
| Student dashboard: available exams, available slots, upcoming exams, booked slots, published results | Done |
| Rules 1 to 10 (windows, capacity, auto Full/Available, own slots only, one booking per exam, history kept, reschedule, change examiner, past data) | Done, checked in the server code |
| JSON API (optional) | Done |
| Charts (optional) | Done: bookings-per-exam bars in plain CSS |
| E-mail notifications (optional) | Not included |

## What every file does

| File | What it does |
| --- | --- |
| `app.py` | Starts everything: creates the Flask app, loads the config, connects the database and Flask-Login, registers the five blueprints (auth, admin, examiner, student, api), creates the tables and the admin. |
| `requirements.txt` | The three packages to install. |
| `backend/config.py` | Secret key and the path of the SQLite file. |
| `backend/models.py` | All database tables as Python classes (list below). |
| `backend/seed.py` | Adds the one admin account if it does not exist yet. |
| `backend/helpers.py` | Shared helpers: reading dates, times and numbers from forms, the search filter, sign-up checks, and the colour used for each status badge. It also holds `can_create_slots()`, `can_book()`, `can_edit_slots()`, `recount_seats()`, `active_booking()`. |
| `backend/decorators.py` | The role check. `role_required("admin")` in `decorators.py`. Each blueprint attaches it to `before_request`, so every route in that file is checked before it runs. |
| `backend/sample_data.py` | Optional demo data. Not used by the running app. |
| `backend/routes/auth.py` | Landing page, login, logout, `/register` (choose Student or Examiner), `/pending` for examiners still waiting for approval. |
| `backend/routes/admin.py` | Everything under `/admin`: dashboard, courses, examinations and their status buttons, rubric, examiners, students, slots, bookings, reschedule, search. |
| `backend/routes/examiner.py` | Everything under `/examiner`: dashboard, assigned exams, slot create/edit/delete, booked students, evaluation. |
| `backend/routes/student.py` | Everything under `/student`: dashboard, exam search, booking and cancelling, history, results, CSV scorecard, profile. |
| `backend/routes/api.py` | Read-only JSON: `/api/exams`, `/api/exams/<id>`, `/api/examiners`, `/api/students`, `/api/bookings`. Needs a logged-in session. |
| `frontend/templates/base.html` | The frame every page uses (CSS links, menu, flash messages). |
| `frontend/templates/_navbar.html`, `_flash.html`, `_empty.html` | The menu (changes with the role), flash message boxes, the "not found" page. |
| `frontend/templates/auth/` | Landing, login, register, pending pages. |
| `frontend/templates/admin/`, `examiner/`, `student/` | One HTML file per screen of that role. |
| `frontend/static/css/style.css` | This project's own colours and layout on top of Bootstrap. |
| `frontend/static/images/` | Small SVG drawings used on the landing, login and empty pages. |

## The database

`config.py` gives the file path, `app.py` calls `db.init_app(app)`, and `db.create_all()` builds any missing table from the classes in `models.py`. Nothing is created by hand.

| Class | Table | Holds |
| --- | --- | --- |
| `User` | `accounts` | every login: admin, examiner or student (`role` column) |
| `Examiner` | `examiner_profiles` | phone, department, approval status |
| `Student` | `student_profiles` | roll number, phone |
| `Course` | `course_catalog` | code, name, description, Active/Inactive |
| `Exam` | `examinations` | type, duration, max marks, the four window dates, status |
| `exam_examiners` | `exam_examiners` | link table: which examiners run which exam |
| `Rubric` | `rubric_criteria` | criterion name, max marks, weightage |
| `ExamSlot` | `exam_slots` | date, start/end time, capacity, available seats, status |
| `Booking` | `slot_bookings` | student + slot + status; never deleted |
| `Evaluation` | `evaluations` | total, remarks, `is_published` flag |
| `Score` | `rubric_scores` | marks for one rubric criterion |

The models use the typed SQLAlchemy 2.0 style: `name: Mapped[str] = mapped_column(String(100))`. Read it as "a column called name that holds a string of up to 100 characters". `Mapped[Optional[...]]` means the column may be empty.

How the rules are enforced: `can_create_slots()`, `can_book()`, `can_edit_slots()`, `recount_seats()`, `active_booking()` in `helpers.py`. The seat counter is `recount_seats(slot)` in `helpers.py`; it runs after every booking, cancellation and reschedule, and flips a slot between Available and Full. How errors reach the user: Small functions such as `signup_problem()` return an error message (or `None`). The route flashes the message and shows the form again.

Exam stages: Draft, then Slot Creation, then Booking Open, then Closed, then Completed. The admin moves an exam forward with the buttons on its page.

## Milestones: what belongs to each one

Use this as the build and commit order. For each milestone, get those parts working, make sure you can explain them, then commit and push with the milestone name in the message. Your commit history should show the work as you really did it, and the report needs an honest AI/LLM declaration (see the MAD-1 instructions).

### M0: Git Tracker and empty app

- .gitignore
- requirements.txt
- README.md (this file, you can trim it at first)
- app.py (only `Flask(__name__)` and `app.run()` at this point)
- backend/__init__.py
- backend/config.py

Done when: Repository exists, `python app.py` starts an empty site.

Commit message: `M0: git tracker and empty app`

### M1: Database models

- backend/models.py
- backend/seed.py
- app.py (now with `db.init_app`, `db.create_all()` and the admin seed)

Done when: Delete the database file, run `python app.py`, and every table plus the admin user comes back.

Commit message: `M1: database models`

### M2: Login and roles

- backend/decorators.py
- backend/helpers.py (form readers and the sign-up checks)
- backend/routes/__init__.py
- backend/routes/auth.py
- frontend/templates/base.html, _navbar.html, _flash.html, _empty.html
- frontend/templates/auth/ (index, login, register, pending)
- frontend/static/css/style.css and frontend/static/images/

Done when: Each role lands on its own dashboard; a student typing an /admin URL is sent back; a new examiner sees the pending page.

Commit message: `M2: login and roles`

### M3: Admin management

- backend/routes/admin.py: dashboard, courses, examinations, exam status buttons, assigning examiners, rubric criteria, examiners (add / approve / reject / deactivate)
- frontend/templates/admin/: dashboard, courses, course_form, exams, exam_form, exam_detail, rubric_form, examiners, examiner_form, examiner_detail

Done when: The admin can create a course, an exam, its rubric, assign examiners and move the exam to Slot Creation.

Commit message: `M3: admin management`

### M4: Examiner slots

- backend/routes/examiner.py: dashboard, profile, exams, exam detail, create / edit / delete slot
- frontend/templates/examiner/: dashboard, profile, exams, exam_detail, slot_form

Done when: Creating a slot outside the window is refused by the server, not just hidden in the page.

Commit message: `M4: examiner slots`

### M5: Student booking

- backend/routes/student.py: dashboard, profile, exam list with search and filters, exam detail, book (confirm page + POST), cancel, history
- frontend/templates/student/: dashboard, profile, exams, exam_detail, confirm, bookings

Done when: A student can book and cancel inside the booking window.

Commit message: `M5: student booking`

### M6: Booking rules

- the seat counter (`recount_seats(slot)` in `helpers.py`)
- one active booking per exam and the full-slot check
- admin.py: all slots, change slot examiner, cancel slot, all bookings, reschedule
- frontend/templates/admin/: slots, bookings, reschedule

Done when: Over-booking and double-booking are both blocked; a full slot turns back to Available when someone cancels.

Commit message: `M6: booking rules`

### M7: Rubric evaluation and results

- examiner.py: slot detail (booked students) and evaluate
- admin.py: the Publish results action
- student.py: results, result detail, CSV scorecard
- frontend/templates/examiner/: slot_detail, evaluate
- frontend/templates/student/: results, result_detail

Done when: An examiner can only grade students in their own slots; students see marks only after publishing.

Commit message: `M7: rubric evaluation and results`

### M8: Search and history

- admin.py: search, students (with the exam filter and booking status), student detail
- frontend/templates/admin/: search, students, student_detail

Done when: Searching by name or ID returns the right rows; a student's cancelled bookings still show in history.

Commit message: `M8: search and history`

### M9: API and polish

- backend/routes/api.py and its line in app.py
- the bookings-per-exam bars on the admin dashboard
- backend/sample_data.py
- final CSS touches

Done when: `/api/exams` returns JSON; every form validates its input.

Commit message: `M9: api and polish`

### M10: Submit

- Project Report.pdf (add it inside this folder)
- final README
- zip the folder (see the end of this file)

Done when: The validation form confirms the zip, and the zip downloaded back from the portal runs.

Commit message: `M10: submit`

## Making the zip

This README is a study guide. It is left out of the zip below; write your own short README or report in your own words.

```bash
cd ..                                     # the folder that contains this project
find "Examination Management Portal" -name "__pycache__" -type d -prune -exec rm -rf {} +
rm -f "Examination Management Portal/backend/examly.sqlite3"
zip -r projectname_<rollno>.zip "Examination Management Portal" -x "*.DS_Store" "*/.gitignore" "*/README.md"
unzip -l projectname_<rollno>.zip         # the root must hold only the project folder
```

# Talent Management Platform for Employee Performance and Career Growth

A full training-platform rebuild in Python/Streamlit: real authentication, real PDF
retrieval-augmented generation (RAG), a voice-enabled AI assistant, and AI-graded exams
with instructor-facing gap analysis.

**v3.0 — Learning Path Builder, email registration, live voice interviews:**
- **Email registration:** when an admin creates a user (or resets a password), the
  login ID and password are emailed automatically via SMTP (`email_utils.py` +
  `TSE_SMTP_*` env vars), with an on-screen fallback if SMTP isn't configured.
- **Learning Path Builder** (`pages/12_Learning_Path_Builder.py`): admins draft
  weeks with 4 frozen reading days (upload a PDF or reuse one from the library) and
  a Day 5 assessment built from three question formats — Choose the correct answer
  (MCQ), Fill in the blanks, and Question & answer — each with its own question
  count and timer. "Generate exam with AI" builds the mixed assessment from that
  week's reading material; weeks publish/unpublish independently.
- **Learning Path** (`pages/13_Learning_Path.py`): the trainee side — each reading
  day unlocks only after the previous one is marked read, and the Day 5 assessment
  unlocks once all 4 days are complete.
- **Interview AI Assistant — Live Interview Mode** (`pages/10_Interview_Prep.py`):
  the voice orb asks each question aloud, listens to the spoken answer, grades it
  with Claude, and auto-advances to the next question, ending with an overall score.

**v2.0 — production pass:** environment-driven config, structured logging, input
validation, a real test suite, Docker deployment, and tactile UI animations.

**v2.1 — learning workflow:** a graduation-course catalog, a course/topic-organized
document library, AI-generated weekly/monthly study timetables with progress
tracking, learner-type personalization, and a voice-enabled interview-prep +
one-click mock test flow triggered when a study-plan topic is completed.

**v2.2 — Admin Control Center & Document Library:** a real analytics dashboard
(8 stat cards, a 30-day assistant-activity chart, an exam score-distribution
chart, and a per-learner rollup table), plus a Document Library page with
in-app PDF preview (page-by-page, zoomable via the browser's own PDF viewer),
download, a fullscreen toggle, and one-click AI summaries.

## Features

- **Login** — hashed credentials (PBKDF2-SHA256, stdlib only, no bcrypt dependency),
  roles (`admin` / `trainee`), employee ID, training domain, and a **learner type**
  (Visual / Auditory / Reading-Writing / Kinesthetic) that personalizes AI-generated
  study plans
- **User Management** *(admin)* — create accounts (auto-generated or manual password,
  learner type), manage users (stats, reset password, delete)
- **Document Ingestion** *(admin)* — upload PDFs tagged to a **course and topic**;
  browse the library either as a flat list or as a course → topic folder tree.
  Comes with a seeded catalog of 24 common graduation courses (B.Tech branches,
  BCA/MCA, B.Sc/M.Sc, B.Com/BBA/MBA, LLB, MBBS, B.Pharm, etc.) — add more from the
  Study Planner or directly in SQLite
- **Knowledge Search** — direct semantic search over the indexed material with a
  Top-K slider
- **AI Assistant** — RAG chat with named sessions, cited sources, a retrieval
  transparency panel, AI-suggested follow-ups, and a voice orb
- **Study Planner** — pick a course and its topics (or add your own), choose a
  length in **weeks or months**, and get an AI-generated week-by-week timetable
  tailored to the learner's style. Check off topics as you complete them — a
  completed topic surfaces a one-click **"Interview + mock test"** action
- **Interview Prep** — generate realistic mock interview questions (mixed
  difficulty, with model answers) for any topic, grounded in indexed material when
  available. The **voice manager** (the same voice-orb component as the AI
  Assistant) speaks each question aloud and listens for a spoken answer; get
  AI feedback comparing your answer to the model answer; or skip straight to a
  **one-click mock test** on the topic, auto-assigned to yourself in My Exams
- **Exam Management** *(admin)* — generate written or voice exams from an indexed
  document (MCQ / very-short / short / long answer), assign to trainees, review results
- **My Exams** *(trainee)* — take assigned exams (typed, or spoken for voice exams),
  instant MCQ scoring, AI grading for written answers
- **Improvement Focus** *(admin)* — AI-generated gap analysis per trainee per exam
- **Document Library** — browse every indexed PDF with an in-app preview (the
  browser's native PDF viewer, embedded — page navigation and zoom included),
  download, a fullscreen toggle, and a one-click AI summary
- **Announcements** — admin publishes, everyone sees them on the home page

The admin **Dashboard** doubles as an Admin Control Center: trainee/active-user
counts, document and knowledge-chunk totals, chat session/message totals, overall
average exam score, a 30-day assistant-activity line chart, an exam score-distribution
bar chart, and a per-learner table (status, exams done/pending, average score).

All data (users, documents, chunks, courses, study plans, interview sets, chat,
exams, attempts, announcements) persists in a local SQLite file
(`talent_sphere.db`) created automatically next to the app.

## 1. Install

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # then fill in ANTHROPIC_API_KEY (see below)
```

## 2. Run

```bash
streamlit run Home.py
```

**First login:** `admin@talentsphere.com` / `admin123` (auto-seeded on first run —
change it or create real accounts right away from User Management). Both the seed
email and password can be overridden via `.env` before first launch.

## 3. Add your Anthropic API key

Needed for: the AI Assistant's answers, exam question generation, grading of
written answers, and improvement-focus analysis. (Document upload/search, MCQ
scoring, user/announcement management all work without it.)

Either put it in `.env` (`ANTHROPIC_API_KEY=sk-ant-...`), export it before launching,
or paste it into the sidebar on the Home page once logged in as admin — the sidebar
value is session-only and always wins if both are set.

## Run with Docker

```bash
cp .env.example .env    # fill in ANTHROPIC_API_KEY
docker compose up --build
```
Visits `http://localhost:8501`. The SQLite database persists in a named Docker
volume (`tse_data`) across restarts and rebuilds.

## Run the tests

```bash
pip install -r requirements.txt   # includes pytest + reportlab for PDF test fixtures
pytest
```
`test_db.py` and `test_validators.py` need nothing but the stdlib + this repo.
`test_auth.py` and `test_rag.py` additionally need Streamlit/pypdf/reportlab
installed (they're skipped automatically if those aren't available, rather than
failing the whole suite).

## What changed in the professional pass (v2.0)

- **Config** — `config.py` centralizes every environment-dependent value (DB path,
  model name, PBKDF2 iterations, lockout thresholds, chunk sizes, log level) read
  from `.env`/environment variables instead of being hardcoded across files.
- **Logging** — `logger.py` gives every module a real logger (console + `app.log`)
  instead of silent `except` blocks; login attempts, failures, and API errors are
  now recorded.
- **Validation** — `validators.py` centralizes email/employee-ID format checks and
  password-strength rules, used consistently in both login and account creation.
- **Login hardening** — repeated failed logins now lock an email out for a
  configurable window (`TSE_MAX_LOGIN_ATTEMPTS` / `TSE_LOGIN_LOCKOUT_MINUTES`),
  tracked in a new `login_attempts` table.
- **Database** — added indexes on every foreign-key column so lookups stay fast
  as data grows, not just on a demo-sized dataset.
- **Tests** — a real `tests/` suite (`pytest`) covering the database layer,
  validators, password hashing, and PDF chunking — see above.
- **Deployment** — `Dockerfile` + `docker-compose.yml` for one-command deployment,
  `.env.example` documenting every setting, `.gitignore` so secrets/DB files never
  get committed.
- **UI motion** — buttons now have real press feedback (scale + a CSS-only ripple
  on tap, no JS), the ~300ms mobile tap delay is removed, cards/tabs/pills settle
  on press, page content fades in smoothly on navigation, and all of it respects
  `prefers-reduced-motion` for users who've asked for less animation.

## How the "AI" parts actually work (so nothing here is a black box)

- **Retrieval** is real TF-IDF + cosine similarity over your uploaded PDFs
  (`scikit-learn`), not a mocked search — try Knowledge Search to see the raw
  retrieval the assistant uses.
- **Generation** (chat answers, exam questions, grading, gap analysis) calls the
  Claude API with the retrieved passages as context.
- **The "How I answered" panel** describes the actual retrieval step taken for that
  message (query → number of chunks/documents retrieved) — it's a transparency log,
  not a simulated tool-call trace.
- **Voice** uses two different mechanisms: the AI Assistant's orb (`voice_orb_static/`)
  is a real bidirectional Streamlit component using the browser's SpeechRecognition
  and SpeechSynthesis APIs, declared via `components.declare_component` (no JS build
  step needed). Voice-exam answers instead use Streamlit's built-in `st.audio_input`
  recorder + the `SpeechRecognition` package (Google's free STT endpoint), which is
  simpler and works per-question. Both need an internet connection and a
  Chromium/Edge/Safari-family browser.

## Project structure

```
Home.py                       # Login gate + dashboard
config.py                     # Environment-driven settings (.env support)
logger.py                     # Shared app logger (console + app.log)
validators.py                 # Email/employee-ID/password validation
auth.py                       # Password hashing, login lockout, session/role guards
db.py                         # SQLite schema + all CRUD
rag.py                        # PDF chunking, TF-IDF search, all Claude calls
theme.py                      # styles.css loader + markup helpers
voice_component.py            # Wraps voice_orb_static/ as a Streamlit component
styles.css                    # LinkedIn-themed stylesheet + touch/motion animations
voice_orb_static/index.html   # Voice orb UI (buildless Streamlit component)
pages/
  1_AI_Assistant.py
  2_Document_Ingestion.py
  3_Knowledge_Search.py
  4_Exam_Management.py
  5_My_Exams.py
  6_Announcements.py
  7_User_Management.py
  8_Improvement_Focus.py
  9_Study_Planner.py
  10_Interview_Prep.py
  11_Document_Library.py
tests/
  conftest.py                 # per-test temp SQLite fixture
  test_db.py, test_validators.py, test_auth.py, test_rag.py
.streamlit/config.toml        # light theme matching styles.css
.env.example                  # every configurable setting, documented
.gitignore
Dockerfile, docker-compose.yml
pytest.ini
requirements.txt
```

## Known limitations (being upfront)

- Exam authoring is AI-generation-only in this build — there's no manual
  question-by-question editor yet.
- TF-IDF is lexical/statistical, not a neural embedding — it's genuinely good at
  matching on shared vocabulary but won't catch pure paraphrases with zero
  overlapping words the way a true embedding model would.
- The voice orb's speech recognition and synthesis run in the browser (Web Speech
  API), so quality/availability depends on the browser and OS, not this app.
- Uploaded PDFs are stored as BLOBs directly inside `talent_sphere.db` so Document
  Library can preview/download them — fine for typical training-material sizes, but
  a large library (many hundreds of MB of PDFs) will make the SQLite file grow
  correspondingly. Move to filesystem/object storage if that becomes a concern.
- The Document Library preview embeds the PDF via a base64 data URI in an
  `<iframe>` — it uses the browser's own built-in PDF viewer (so page navigation
  and zoom come for free), but very large PDFs (dozens of MB) may load slowly
  since the whole file is inlined into the page.

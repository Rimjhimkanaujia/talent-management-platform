"""SQLite persistence layer for Talent Management Platform — Pro edition."""
import sqlite3
import json
import datetime
import config
from logger import get_logger

log = get_logger(__name__)
DB_PATH = config.DB_PATH


def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id TEXT UNIQUE, name TEXT, email TEXT UNIQUE,
        password_hash TEXT, salt TEXT, role TEXT, domain TEXT, learner_type TEXT,
        status TEXT DEFAULT 'active', created_at TEXT, last_login TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS documents(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT, pages INTEGER, size_kb REAL, course_id INTEGER, topic TEXT,
        uploaded_by TEXT, uploaded_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS chunks(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER, page INTEGER, chunk_index INTEGER, text TEXT,
        FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE)""")
    c.execute("""CREATE TABLE IF NOT EXISTS chat_sessions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, title TEXT, created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS chat_messages(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER, role TEXT, content TEXT,
        sources_json TEXT, followups_json TEXT, created_at TEXT,
        FOREIGN KEY(session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE)""")
    c.execute("""CREATE TABLE IF NOT EXISTS exams(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT, description TEXT, exam_type TEXT,
        source_document_id INTEGER, questions_json TEXT,
        created_by TEXT, created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS exam_assignments(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exam_id INTEGER, user_id INTEGER, status TEXT DEFAULT 'pending', assigned_at TEXT,
        FOREIGN KEY(exam_id) REFERENCES exams(id) ON DELETE CASCADE)""")
    c.execute("""CREATE TABLE IF NOT EXISTS exam_attempts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exam_id INTEGER, user_id INTEGER, answers_json TEXT,
        score REAL, max_score REAL, feedback_json TEXT, submitted_at TEXT,
        FOREIGN KEY(exam_id) REFERENCES exams(id) ON DELETE CASCADE)""")
    c.execute("""CREATE TABLE IF NOT EXISTS announcements(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT, message TEXT, category TEXT, created_by TEXT, created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS login_attempts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT, success INTEGER, attempted_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS courses(
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)""")
    c.execute("""CREATE TABLE IF NOT EXISTS study_plans(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, course_id INTEGER, title TEXT, duration_weeks INTEGER,
        plan_json TEXT, progress_json TEXT, created_at TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE)""")
    c.execute("""CREATE TABLE IF NOT EXISTS interview_sets(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, topic TEXT, questions_json TEXT, created_at TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE)""")
    # ---------------- Learning Path Builder ----------------
    c.execute("""CREATE TABLE IF NOT EXISTS learning_path_weeks(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        week_number INTEGER,
        title TEXT,
        day1_doc_id INTEGER, day2_doc_id INTEGER, day3_doc_id INTEGER, day4_doc_id INTEGER,
        formats_json TEXT,
        exam_id INTEGER,
        exam_generated_at TEXT,
        published INTEGER DEFAULT 0,
        published_at TEXT,
        created_by TEXT, created_at TEXT,
        FOREIGN KEY(exam_id) REFERENCES exams(id) ON DELETE SET NULL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS learning_path_progress(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        week_id INTEGER, user_id INTEGER, day_number INTEGER,
        status TEXT DEFAULT 'pending', updated_at TEXT,
        UNIQUE(week_id, user_id, day_number),
        FOREIGN KEY(week_id) REFERENCES learning_path_weeks(id) ON DELETE CASCADE,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE)""")

    # --- migrations: safely add columns that may be missing on a DB created by an older version ---
    for table, coldef in [
        ("users", "learner_type TEXT"),
        ("documents", "course_id INTEGER"),
        ("documents", "topic TEXT"),
        ("documents", "file_blob BLOB"),
    ]:
        try:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {coldef}")
        except sqlite3.OperationalError:
            pass  # column already exists

    # indexes that matter once there's real data volume
    c.execute("CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON chat_messages(session_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON chat_sessions(user_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_assignments_user ON exam_assignments(user_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_assignments_exam ON exam_assignments(exam_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_attempts_user ON exam_attempts(user_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_login_attempts_email ON login_attempts(email, attempted_at)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_lp_progress_week ON learning_path_progress(week_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_lp_progress_user ON learning_path_progress(user_id)")

    conn.commit()
    conn.close()
    log.debug("Database initialized at %s", DB_PATH)

    if not get_courses():
        seed_default_courses()


# ---------------- Login attempt tracking (lockout support) ----------------
def record_login_attempt(email, success):
    conn = get_conn()
    conn.execute("INSERT INTO login_attempts(email,success,attempted_at) VALUES (?,?,?)",
                 (email.strip().lower(), int(success), now()))
    conn.commit(); conn.close()

def recent_failed_attempts(email, since_iso):
    conn = get_conn()
    n = conn.execute(
        "SELECT COUNT(*) c FROM login_attempts WHERE email=? AND success=0 AND attempted_at>=?",
        (email.strip().lower(), since_iso)
    ).fetchone()["c"]
    conn.close()
    return n


# ---------------- Users ----------------
def create_user(employee_id, name, email, password_hash, salt, role, domain, learner_type=None):
    conn = get_conn()
    conn.execute("""INSERT INTO users(employee_id,name,email,password_hash,salt,role,domain,learner_type,status,created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?)""",
                 (employee_id, name, email, password_hash, salt, role, domain, learner_type, "active", now()))
    conn.commit(); conn.close()

def get_user_by_email(email):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_by_id(uid):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_users(role=None):
    conn = get_conn()
    if role:
        rows = conn.execute("SELECT * FROM users WHERE role=? ORDER BY id DESC", (role,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM users ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_last_login(uid):
    conn = get_conn()
    conn.execute("UPDATE users SET last_login=?, status='active' WHERE id=?", (now(), uid))
    conn.commit(); conn.close()

def set_password(uid, password_hash, salt):
    conn = get_conn()
    conn.execute("UPDATE users SET password_hash=?, salt=? WHERE id=?", (password_hash, salt, uid))
    conn.commit(); conn.close()

def delete_user(uid):
    conn = get_conn()
    conn.execute("DELETE FROM users WHERE id=?", (uid,))
    conn.commit(); conn.close()

def count_active_users():
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) c FROM users WHERE status='active'").fetchone()["c"]
    conn.close()
    return n


# ---------------- Documents & chunks ----------------
def add_document(filename, pages, size_kb, uploaded_by, course_id=None, topic=None, file_blob=None):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO documents(filename,pages,size_kb,course_id,topic,file_blob,uploaded_by,uploaded_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (filename, pages, size_kb, course_id, topic, file_blob, uploaded_by, now()))
    conn.commit(); did = cur.lastrowid; conn.close()
    return did

def get_document_blob(did):
    conn = get_conn()
    row = conn.execute("SELECT file_blob FROM documents WHERE id=?", (did,)).fetchone()
    conn.close()
    return row["file_blob"] if row else None

def add_chunks(document_id, chunks):
    """chunks: list of (page, chunk_index, text)"""
    conn = get_conn()
    conn.executemany("INSERT INTO chunks(document_id,page,chunk_index,text) VALUES (?,?,?,?)",
                      [(document_id, p, i, t) for p, i, t in chunks])
    conn.commit(); conn.close()

def get_documents():
    conn = get_conn()
    rows = conn.execute("""SELECT documents.id, documents.filename, documents.pages, documents.size_kb,
                                  documents.course_id, documents.topic, documents.uploaded_by, documents.uploaded_at,
                                  courses.name as course_name
                           FROM documents LEFT JOIN courses ON documents.course_id = courses.id
                           ORDER BY documents.id DESC""").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_documents_by_course(course_id):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM documents WHERE course_id=? ORDER BY topic, id", (course_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_topics_for_course(course_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT topic FROM documents WHERE course_id=? AND topic IS NOT NULL AND topic!='' ORDER BY topic",
        (course_id,)).fetchall()
    conn.close()
    return [r["topic"] for r in rows]

def get_document(did):
    conn = get_conn()
    row = conn.execute("SELECT * FROM documents WHERE id=?", (did,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_chunks():
    conn = get_conn()
    rows = conn.execute("""SELECT chunks.id, chunks.page, chunks.text, documents.filename, documents.id as doc_id
                           FROM chunks JOIN documents ON chunks.document_id = documents.id""").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def count_chunks():
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) c FROM chunks").fetchone()["c"]
    conn.close()
    return n

def get_chunks_for_document(did):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM chunks WHERE document_id=? ORDER BY page, chunk_index", (did,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------- Chat sessions & messages ----------------
def create_session(user_id, title):
    conn = get_conn()
    cur = conn.execute("INSERT INTO chat_sessions(user_id,title,created_at) VALUES (?,?,?)", (user_id, title, now()))
    conn.commit(); sid = cur.lastrowid; conn.close()
    return sid

def get_sessions(user_id):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM chat_sessions WHERE user_id=? ORDER BY id DESC", (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def rename_session(sid, title):
    conn = get_conn()
    conn.execute("UPDATE chat_sessions SET title=? WHERE id=?", (title, sid))
    conn.commit(); conn.close()

def delete_session(sid):
    conn = get_conn()
    conn.execute("DELETE FROM chat_sessions WHERE id=?", (sid,))
    conn.commit(); conn.close()

def add_message(session_id, role, content, sources=None, followups=None):
    conn = get_conn()
    conn.execute("""INSERT INTO chat_messages(session_id,role,content,sources_json,followups_json,created_at)
                    VALUES (?,?,?,?,?,?)""",
                 (session_id, role, content, json.dumps(sources or []), json.dumps(followups or []), now()))
    conn.commit(); conn.close()

def get_messages(session_id):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM chat_messages WHERE session_id=? ORDER BY id", (session_id,)).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["sources"] = json.loads(d["sources_json"] or "[]")
        d["followups"] = json.loads(d["followups_json"] or "[]")
        out.append(d)
    return out


# ---------------- Exams ----------------
def save_exam(title, description, exam_type, source_document_id, questions, created_by):
    conn = get_conn()
    cur = conn.execute("""INSERT INTO exams(title,description,exam_type,source_document_id,questions_json,created_by,created_at)
                          VALUES (?,?,?,?,?,?,?)""",
                        (title, description, exam_type, source_document_id, json.dumps(questions), created_by, now()))
    conn.commit(); eid = cur.lastrowid; conn.close()
    return eid

def get_exams():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM exams ORDER BY id DESC").fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r); d["questions"] = json.loads(d["questions_json"]); out.append(d)
    return out

def get_exam(eid):
    conn = get_conn()
    row = conn.execute("SELECT * FROM exams WHERE id=?", (eid,)).fetchone()
    conn.close()
    if not row: return None
    d = dict(row); d["questions"] = json.loads(d["questions_json"])
    return d

def assign_exam(exam_id, user_ids):
    conn = get_conn()
    conn.executemany("INSERT INTO exam_assignments(exam_id,user_id,status,assigned_at) VALUES (?,?,?,?)",
                      [(exam_id, uid, "pending", now()) for uid in user_ids])
    conn.commit(); conn.close()

def get_assignments_for_user(user_id, status=None):
    conn = get_conn()
    if status:
        rows = conn.execute("SELECT * FROM exam_assignments WHERE user_id=? AND status=?", (user_id, status)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM exam_assignments WHERE user_id=?", (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_assignments_for_exam(exam_id):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM exam_assignments WHERE exam_id=?", (exam_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def mark_assignment_complete(exam_id, user_id):
    conn = get_conn()
    conn.execute("UPDATE exam_assignments SET status='completed' WHERE exam_id=? AND user_id=?", (exam_id, user_id))
    conn.commit(); conn.close()

def save_attempt(exam_id, user_id, answers, score, max_score, feedback):
    conn = get_conn()
    conn.execute("""INSERT INTO exam_attempts(exam_id,user_id,answers_json,score,max_score,feedback_json,submitted_at)
                    VALUES (?,?,?,?,?,?,?)""",
                 (exam_id, user_id, json.dumps(answers), score, max_score, json.dumps(feedback), now()))
    conn.commit(); conn.close()
    mark_assignment_complete(exam_id, user_id)

def get_attempts(user_id=None, exam_id=None):
    conn = get_conn()
    q = "SELECT * FROM exam_attempts WHERE 1=1"
    params = []
    if user_id: q += " AND user_id=?"; params.append(user_id)
    if exam_id: q += " AND exam_id=?"; params.append(exam_id)
    q += " ORDER BY id DESC"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["answers"] = json.loads(d["answers_json"])
        d["feedback"] = json.loads(d["feedback_json"])
        out.append(d)
    return out


# ---------------- Announcements ----------------
def add_announcement(title, message, category, created_by):
    conn = get_conn()
    conn.execute("INSERT INTO announcements(title,message,category,created_by,created_at) VALUES (?,?,?,?,?)",
                 (title, message, category, created_by, now()))
    conn.commit(); conn.close()

def get_announcements():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM announcements ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------- Courses ----------------
def seed_default_courses():
    import config
    conn = get_conn()
    conn.executemany("INSERT OR IGNORE INTO courses(name) VALUES (?)",
                      [(c,) for c in config.DEFAULT_COURSES])
    conn.commit(); conn.close()

def get_courses():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM courses ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_course(cid):
    conn = get_conn()
    row = conn.execute("SELECT * FROM courses WHERE id=?", (cid,)).fetchone()
    conn.close()
    return dict(row) if row else None

def add_course(name):
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO courses(name) VALUES (?)", (name,))
    conn.commit(); conn.close()


# ---------------- Study plans ----------------
def save_study_plan(user_id, course_id, title, duration_weeks, plan):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO study_plans(user_id,course_id,title,duration_weeks,plan_json,progress_json,created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (user_id, course_id, title, duration_weeks, json.dumps(plan), json.dumps({}), now()))
    conn.commit(); pid = cur.lastrowid; conn.close()
    return pid

def get_study_plans(user_id):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM study_plans WHERE user_id=? ORDER BY id DESC", (user_id,)).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["plan"] = json.loads(d["plan_json"])
        d["progress"] = json.loads(d["progress_json"] or "{}")
        out.append(d)
    return out

def get_study_plan(pid):
    conn = get_conn()
    row = conn.execute("SELECT * FROM study_plans WHERE id=?", (pid,)).fetchone()
    conn.close()
    if not row: return None
    d = dict(row)
    d["plan"] = json.loads(d["plan_json"])
    d["progress"] = json.loads(d["progress_json"] or "{}")
    return d

def set_topic_progress(plan_id, topic, status):
    """status: 'pending' | 'in_progress' | 'completed'"""
    plan = get_study_plan(plan_id)
    if not plan:
        return
    progress = plan["progress"]
    progress[topic] = status
    conn = get_conn()
    conn.execute("UPDATE study_plans SET progress_json=? WHERE id=?", (json.dumps(progress), plan_id))
    conn.commit(); conn.close()

def delete_study_plan(pid):
    conn = get_conn()
    conn.execute("DELETE FROM study_plans WHERE id=?", (pid,))
    conn.commit(); conn.close()


# ---------------- Interview prep sets ----------------
def save_interview_set(user_id, topic, questions):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO interview_sets(user_id,topic,questions_json,created_at) VALUES (?,?,?,?)",
        (user_id, topic, json.dumps(questions), now()))
    conn.commit(); iid = cur.lastrowid; conn.close()
    return iid

def get_interview_sets(user_id):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM interview_sets WHERE user_id=? ORDER BY id DESC", (user_id,)).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r); d["questions"] = json.loads(d["questions_json"]); out.append(d)
    return out

def get_interview_set(iid):
    conn = get_conn()
    row = conn.execute("SELECT * FROM interview_sets WHERE id=?", (iid,)).fetchone()
    conn.close()
    if not row: return None
    d = dict(row); d["questions"] = json.loads(d["questions_json"])
    return d


# ---------------- Learning Path Builder ----------------
def draft_next_week(created_by):
    conn = get_conn()
    last = conn.execute("SELECT MAX(week_number) m FROM learning_path_weeks").fetchone()["m"]
    week_number = (last or 0) + 1
    default_formats = {
        "mcq": {"label": "Choose the correct answer", "enabled": True, "questions": 5, "timer_min": 10},
        "fillblank": {"label": "Fill in the blanks", "enabled": True, "questions": 5, "timer_min": 10},
        "qa": {"label": "Question & answer", "enabled": True, "questions": 5, "timer_min": 10},
    }
    cur = conn.execute(
        """INSERT INTO learning_path_weeks(week_number,title,formats_json,published,created_by,created_at)
           VALUES (?,?,?,0,?,?)""",
        (week_number, f"Week {week_number}", json.dumps(default_formats), created_by, now()))
    conn.commit(); wid = cur.lastrowid; conn.close()
    return wid

def get_learning_path_weeks():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM learning_path_weeks ORDER BY week_number").fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["formats"] = json.loads(d["formats_json"] or "{}")
        out.append(d)
    return out

def get_learning_path_week(wid):
    conn = get_conn()
    row = conn.execute("SELECT * FROM learning_path_weeks WHERE id=?", (wid,)).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["formats"] = json.loads(d["formats_json"] or "{}")
    return d

def set_week_day_document(wid, day_number, document_id):
    col = f"day{day_number}_doc_id"
    conn = get_conn()
    conn.execute(f"UPDATE learning_path_weeks SET {col}=? WHERE id=?", (document_id, wid))
    conn.commit(); conn.close()

def save_week_formats(wid, formats):
    conn = get_conn()
    conn.execute("UPDATE learning_path_weeks SET formats_json=? WHERE id=?", (json.dumps(formats), wid))
    conn.commit(); conn.close()

def set_week_exam(wid, exam_id):
    conn = get_conn()
    conn.execute("UPDATE learning_path_weeks SET exam_id=?, exam_generated_at=? WHERE id=?", (exam_id, now(), wid))
    conn.commit(); conn.close()

def set_week_published(wid, published):
    conn = get_conn()
    conn.execute("UPDATE learning_path_weeks SET published=?, published_at=? WHERE id=?",
                 (int(published), now() if published else None, wid))
    conn.commit(); conn.close()

def delete_week(wid):
    conn = get_conn()
    conn.execute("DELETE FROM learning_path_weeks WHERE id=?", (wid,))
    conn.commit(); conn.close()

def get_published_weeks():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM learning_path_weeks WHERE published=1 ORDER BY week_number").fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["formats"] = json.loads(d["formats_json"] or "{}")
        out.append(d)
    return out

def set_day_progress(week_id, user_id, day_number, status):
    conn = get_conn()
    conn.execute(
        """INSERT INTO learning_path_progress(week_id,user_id,day_number,status,updated_at)
           VALUES (?,?,?,?,?)
           ON CONFLICT(week_id,user_id,day_number) DO UPDATE SET status=excluded.status, updated_at=excluded.updated_at""",
        (week_id, user_id, day_number, status, now()))
    conn.commit(); conn.close()

def get_week_progress(week_id, user_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT day_number, status FROM learning_path_progress WHERE week_id=? AND user_id=?",
        (week_id, user_id)).fetchall()
    conn.close()
    return {r["day_number"]: r["status"] for r in rows}


# ---------------- Dashboard analytics ----------------
def count_sessions():
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) c FROM chat_sessions").fetchone()["c"]
    conn.close()
    return n

def count_messages():
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) c FROM chat_messages").fetchone()["c"]
    conn.close()
    return n

def messages_per_day(days=30):
    """Returns a list of (date_str, count) for the last `days` days, oldest first, zero-filled."""
    conn = get_conn()
    since = (datetime.datetime.now() - datetime.timedelta(days=days)).date().isoformat()
    rows = conn.execute(
        "SELECT substr(created_at,1,10) d, COUNT(*) c FROM chat_messages WHERE substr(created_at,1,10)>=? "
        "GROUP BY d ORDER BY d", (since,)
    ).fetchall()
    conn.close()
    counts = {r["d"]: r["c"] for r in rows}
    out = []
    for i in range(days, -1, -1):
        d = (datetime.datetime.now() - datetime.timedelta(days=i)).date().isoformat()
        out.append((d, counts.get(d, 0)))
    return out

def score_distribution():
    """Returns a list of (bucket_label, count) across 10%-wide buckets, based on all exam attempts."""
    conn = get_conn()
    rows = conn.execute("SELECT score, max_score FROM exam_attempts WHERE max_score>0").fetchall()
    conn.close()
    buckets = {f"{i}-{i+10}%": 0 for i in range(0, 100, 10)}
    for r in rows:
        pct = max(0, min(99, (r["score"] / r["max_score"]) * 100))
        bucket_start = int(pct // 10) * 10
        buckets[f"{bucket_start}-{bucket_start+10}%"] += 1
    return list(buckets.items())

def learners_summary():
    """Per-trainee rollup: name, status, completed exams, pending exams, average score %."""
    trainees = get_users(role="trainee")
    out = []
    for t in trainees:
        assignments = get_assignments_for_user(t["id"])
        done = sum(1 for a in assignments if a["status"] == "completed")
        pending = sum(1 for a in assignments if a["status"] == "pending")
        attempts = get_attempts(user_id=t["id"])
        avg = round(sum(a["score"] / a["max_score"] * 100 for a in attempts if a["max_score"]) / len(attempts)) if attempts else 0
        out.append({"name": t["name"], "status": t["status"], "done": done, "pending": pending, "avg": avg})
    return out

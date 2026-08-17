import datetime


def test_init_db_creates_tables(temp_db):
    conn = temp_db.get_conn()
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    conn.close()
    expected = {"users", "documents", "chunks", "chat_sessions", "chat_messages",
                "exams", "exam_assignments", "exam_attempts", "announcements", "login_attempts"}
    assert expected.issubset(tables)


def test_user_crud(temp_db):
    temp_db.create_user("EMP-1", "Priya Sharma", "priya@company.com", "hash", "salt", "trainee", "general")
    u = temp_db.get_user_by_email("priya@company.com")
    assert u["name"] == "Priya Sharma"
    assert u["role"] == "trainee"

    users = temp_db.get_users()
    assert len(users) == 1

    temp_db.set_password(u["id"], "newhash", "newsalt")
    u2 = temp_db.get_user_by_id(u["id"])
    assert u2["password_hash"] == "newhash"

    temp_db.delete_user(u["id"])
    assert temp_db.get_user_by_email("priya@company.com") is None


def test_login_attempt_lockout_window(temp_db):
    temp_db.record_login_attempt("a@b.com", False)
    temp_db.record_login_attempt("a@b.com", False)
    temp_db.record_login_attempt("a@b.com", True)
    since = (datetime.datetime.now() - datetime.timedelta(minutes=10)).isoformat(timespec="seconds")
    assert temp_db.recent_failed_attempts("a@b.com", since) == 2


def test_document_and_chunks(temp_db):
    did = temp_db.add_document("sample.pdf", 3, 120.5, "admin@x.com")
    temp_db.add_chunks(did, [(1, 0, "chunk one text"), (1, 1, "chunk two text")])
    assert temp_db.count_chunks() == 2
    chunks = temp_db.get_chunks_for_document(did)
    assert len(chunks) == 2
    assert chunks[0]["page"] == 1


def test_chat_session_and_messages(temp_db):
    temp_db.create_user("EMP-1", "A", "a@b.com", "h", "s", "trainee", "general")
    u = temp_db.get_user_by_email("a@b.com")
    sid = temp_db.create_session(u["id"], "ML basics")
    temp_db.add_message(sid, "user", "What is EPCIS?")
    temp_db.add_message(sid, "assistant", "EPCIS is...",
                         sources=[{"filename": "x.pdf", "page": 1, "score": 0.8}],
                         followups=["What is GS1?"])
    msgs = temp_db.get_messages(sid)
    assert len(msgs) == 2
    assert msgs[1]["sources"][0]["filename"] == "x.pdf"
    assert msgs[1]["followups"] == ["What is GS1?"]

    temp_db.delete_session(sid)
    assert temp_db.get_messages(sid) == []


def test_exam_lifecycle(temp_db):
    temp_db.create_user("EMP-1", "Trainee One", "t1@b.com", "h", "s", "trainee", "general")
    u = temp_db.get_user_by_email("t1@b.com")
    eid = temp_db.save_exam("Module 1", "desc", "mcq", None,
                            [{"question": "2+2?", "type": "mcq", "options": ["3", "4"],
                              "correct_index": 1, "explanation": "basic math"}],
                            "admin@x.com")
    temp_db.assign_exam(eid, [u["id"]])
    assignments = temp_db.get_assignments_for_user(u["id"])
    assert assignments[0]["status"] == "pending"

    temp_db.save_attempt(eid, u["id"], {0: 1}, 1, 1, [{"score": 1, "feedback": "Correct."}])
    assignments = temp_db.get_assignments_for_user(u["id"])
    assert assignments[0]["status"] == "completed"

    attempts = temp_db.get_attempts(user_id=u["id"])
    assert attempts[0]["score"] == 1


def test_announcements(temp_db):
    temp_db.add_announcement("Kickoff", "Welcome!", "General", "admin@x.com")
    anns = temp_db.get_announcements()
    assert len(anns) == 1
    assert anns[0]["title"] == "Kickoff"


def test_courses_seeded_on_init(temp_db):
    courses = temp_db.get_courses()
    assert len(courses) > 0
    assert any("B.Tech" in c["name"] for c in courses)


def test_document_course_and_topic_tagging(temp_db):
    course = temp_db.get_courses()[0]
    did = temp_db.add_document("dsa.pdf", 5, 100.0, "admin@x.com", course_id=course["id"], topic="Arrays")
    docs = temp_db.get_documents()
    tagged = next(d for d in docs if d["id"] == did)
    assert tagged["topic"] == "Arrays"
    assert tagged["course_name"] == course["name"]
    assert "Arrays" in temp_db.get_topics_for_course(course["id"])


def test_user_learner_type(temp_db):
    temp_db.create_user("EMP-1", "A B", "a@b.com", "h", "s", "trainee", "general", learner_type="Visual")
    u = temp_db.get_user_by_email("a@b.com")
    assert u["learner_type"] == "Visual"


def test_study_plan_progress_tracking(temp_db):
    temp_db.create_user("EMP-1", "A B", "a@b.com", "h", "s", "trainee", "general")
    u = temp_db.get_user_by_email("a@b.com")
    course = temp_db.get_courses()[0]
    plan = {"weeks": [{"week": 1, "label": "Week 1", "topics": ["Arrays", "Linked Lists"]}]}
    pid = temp_db.save_study_plan(u["id"], course["id"], "Test Plan", 1, plan)

    fetched = temp_db.get_study_plan(pid)
    assert fetched["progress"] == {}

    temp_db.set_topic_progress(pid, "Arrays", "completed")
    fetched = temp_db.get_study_plan(pid)
    assert fetched["progress"]["Arrays"] == "completed"
    assert "Linked Lists" not in fetched["progress"]

    plans = temp_db.get_study_plans(u["id"])
    assert len(plans) == 1

    temp_db.delete_study_plan(pid)
    assert temp_db.get_study_plan(pid) is None


def test_interview_sets(temp_db):
    temp_db.create_user("EMP-1", "A B", "a@b.com", "h", "s", "trainee", "general")
    u = temp_db.get_user_by_email("a@b.com")
    questions = [{"question": "What is an array?", "model_answer": "...", "difficulty": "easy"}]
    iid = temp_db.save_interview_set(u["id"], "Arrays", questions)

    fetched = temp_db.get_interview_set(iid)
    assert fetched["topic"] == "Arrays"
    assert len(fetched["questions"]) == 1

    all_sets = temp_db.get_interview_sets(u["id"])
    assert len(all_sets) == 1


def test_document_blob_roundtrip(temp_db):
    blob = b"%PDF-1.4 fake pdf bytes"
    did = temp_db.add_document("test.pdf", 1, 1.0, "admin@x.com", file_blob=blob)
    assert temp_db.get_document_blob(did) == blob
    # listing should not carry the blob (keeps it lightweight)
    listed = temp_db.get_documents()[0]
    assert "file_blob" not in listed


def test_dashboard_counts_and_activity(temp_db):
    temp_db.create_user("EMP-1", "A B", "a@b.com", "h", "s", "trainee", "general")
    u = temp_db.get_user_by_email("a@b.com")
    sid = temp_db.create_session(u["id"], "ML")
    temp_db.add_message(sid, "user", "Hi")
    temp_db.add_message(sid, "assistant", "Hello")

    assert temp_db.count_sessions() == 1
    assert temp_db.count_messages() == 2

    activity = temp_db.messages_per_day(30)
    assert len(activity) == 31  # inclusive of today
    assert activity[-1][1] == 2  # today's message count


def test_score_distribution_buckets(temp_db):
    temp_db.create_user("EMP-1", "A B", "a@b.com", "h", "s", "trainee", "general")
    u = temp_db.get_user_by_email("a@b.com")
    eid = temp_db.save_exam("Mod 1", "d", "mcq", None,
                            [{"question": "q", "type": "mcq", "options": ["a", "b"], "correct_index": 0}],
                            "admin@x.com")
    temp_db.save_attempt(eid, u["id"], {0: 0}, 4, 10, [{"score": 4, "feedback": "ok"}])  # 40%
    dist = dict(temp_db.score_distribution())
    assert dist["40-50%"] == 1
    assert sum(dist.values()) == 1


def test_learners_summary_matches_progress(temp_db):
    temp_db.create_user("EMP-1", "Shahul Hameed", "sh@x.com", "h", "s", "trainee", "general")
    u = temp_db.get_user_by_email("sh@x.com")
    eid1 = temp_db.save_exam("Mod 1", "d", "mcq", None, [{"question": "q"}], "admin@x.com")
    eid2 = temp_db.save_exam("Mod 2", "d", "mcq", None, [{"question": "q"}], "admin@x.com")
    temp_db.assign_exam(eid1, [u["id"]])
    temp_db.assign_exam(eid2, [u["id"]])
    temp_db.save_attempt(eid1, u["id"], {0: 0}, 4, 10, [{"score": 4, "feedback": "ok"}])

    summary = temp_db.learners_summary()
    assert len(summary) == 1
    row = summary[0]
    assert row["name"] == "Shahul Hameed"
    assert row["done"] == 1
    assert row["pending"] == 1
    assert row["avg"] == 40

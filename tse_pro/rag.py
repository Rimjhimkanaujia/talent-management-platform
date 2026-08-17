"""PDF ingestion + TF-IDF retrieval + Claude calls for Talent Management Platform."""
import json
import os
import streamlit as st
import config
from logger import get_logger

log = get_logger(__name__)
MODEL = config.ANTHROPIC_MODEL


# ==================== Claude API ====================
def get_api_key():
    return st.session_state.get("api_key") or os.environ.get("ANTHROPIC_API_KEY", "") or config.ANTHROPIC_API_KEY


def get_client():
    key = get_api_key()
    if not key:
        return None
    from anthropic import Anthropic
    return Anthropic(api_key=key)


def ask_claude(system, user_text, json_mode=False, max_tokens=1200):
    client = get_client()
    if client is None:
        raise RuntimeError("No Anthropic API key set — add one on the Home page sidebar, "
                            "or set the ANTHROPIC_API_KEY environment variable.")
    try:
        resp = client.messages.create(
            model=MODEL, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": user_text}],
        )
    except Exception:
        log.exception("Claude API call failed")
        raise
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
    if json_mode:
        text = text.replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            log.error("Claude returned non-JSON when JSON was requested: %s", text[:300])
            raise
    return text


# ==================== PDF ingestion ====================
def extract_pdf_chunks(file_bytes, words_per_chunk=None, overlap=None):
    """Returns (num_pages, chunks) where chunks is a list of (page, chunk_index, text)."""
    words_per_chunk = words_per_chunk or config.CHUNK_WORDS
    overlap = overlap if overlap is not None else config.CHUNK_OVERLAP
    from pypdf import PdfReader
    import io
    reader = PdfReader(io.BytesIO(file_bytes))
    chunks = []
    for page_num, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if not text:
            continue
        words = text.split()
        idx = 0
        i = 0
        while i < len(words):
            piece = " ".join(words[i:i + words_per_chunk])
            if piece.strip():
                chunks.append((page_num, idx, piece))
                idx += 1
            i += words_per_chunk - overlap if words_per_chunk > overlap else words_per_chunk
    return len(reader.pages), chunks


# ==================== TF-IDF semantic search ====================
@st.cache_resource(show_spinner=False)
def _build_index(_version):
    """_version is a cache-busting int (e.g. total chunk count) so this rebuilds after ingestion."""
    import db
    from sklearn.feature_extraction.text import TfidfVectorizer
    rows = db.get_all_chunks()
    if not rows:
        return None, None, []
    texts = [r["text"] for r in rows]
    vec = TfidfVectorizer(stop_words="english", max_features=20000)
    matrix = vec.fit_transform(texts)
    return vec, matrix, rows


def search(query, top_k=None):
    import db
    from sklearn.metrics.pairwise import cosine_similarity
    top_k = top_k or config.DEFAULT_TOP_K
    version = db.count_chunks()
    vec, matrix, rows = _build_index(version)
    if vec is None:
        return []
    q_vec = vec.transform([query])
    sims = cosine_similarity(q_vec, matrix)[0]
    ranked = sorted(range(len(rows)), key=lambda i: sims[i], reverse=True)[:top_k]
    results = []
    for i in ranked:
        if sims[i] <= 0:
            continue
        r = rows[i]
        results.append({
            "filename": r["filename"], "page": r["page"],
            "text": r["text"], "score": round(float(sims[i]), 3),
        })
    log.debug("search(%r) -> %d results", query[:60], len(results))
    return results


# ==================== RAG chat ====================
def ask_assistant(query, top_k=None, history=None, domain=None):
    top_k = top_k or config.DEFAULT_TOP_K
    sources = search(query, top_k=top_k)
    context = "\n\n".join(
        f"[Source {i+1}: {s['filename']}, page {s['page']}]\n{s['text']}"
        for i, s in enumerate(sources)
    ) or "(no matching material found in the document index)"

    history_block = ""
    if history:
        history_block = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in history[-6:])

    sys = (
        "You are the Talent AI Assistant inside Talent Management Platform, a corporate training platform"
        + (f" focused on {domain}" if domain and domain != "general" else "")
        + ". Answer the trainee's question using the provided source excerpts when relevant — cite them "
          "naturally in prose (e.g. 'as covered in the training material...') without inventing facts not "
          "in the sources or your general knowledge. Be clear, encouraging, and concise. If the sources don't "
          "cover the question, answer from general knowledge and say so briefly. "
          "End your reply naturally (e.g. offering to schedule a follow-up or assign a quiz) when appropriate.\n\n"
          'Output ONLY valid JSON, no markdown fences: {"answer":"...", "followups":["q1","q2","q3"]} '
          "where followups are 3 short natural follow-up questions the trainee might ask next, "
          "grounded in the same topic/sources."
    )
    user_msg = f"Conversation so far:\n{history_block}\n\nSource excerpts:\n{context}\n\nTrainee question: {query}"
    data = ask_claude(sys, user_msg, json_mode=True)
    return data.get("answer", ""), data.get("followups", []), sources


# ==================== Exam generation & grading ====================
QUESTION_TYPES = {
    "mcq": ("Multiple choice", 1),
    "vshort": ("Very short answer (1-2 marks)", 2),
    "short": ("Short answer (3-5 marks)", 5),
    "long": ("Long answer (8-10 marks)", 10),
    "truefalse": ("True / False", 1),
    "fillblank": ("Fill in the blanks", 1),
    "qa": ("Question & answer", 5),
}


def generate_exam_questions(topic_or_context, count, qtype):
    type_spec = {
        "mcq": ('Use this shape: {"questions":[{"question":"...","type":"mcq",'
                '"options":["...","...","...","..."],"correct_index":0,"explanation":"one sentence"}]}'),
        "vshort": ('Use this shape: {"questions":[{"question":"...","type":"vshort",'
                   '"model_answer":"a 1-2 sentence ideal answer","rubric":"what a full-marks answer must state"}]} '
                   '— worth 1-2 marks each.'),
        "short": ('Use this shape: {"questions":[{"question":"...","type":"short",'
                  '"model_answer":"a concise ideal answer","rubric":"2-3 key points"}]} — worth 3-5 marks each.'),
        "long": ('Use this shape: {"questions":[{"question":"...","type":"long",'
                 '"model_answer":"a full model answer","rubric":"the distinct points a full-marks answer must include"}]} '
                 '— worth 8-10 marks each.'),
        "truefalse": ('Use this shape: {"questions":[{"question":"a statement that is either true or false",'
                      '"type":"truefalse","correct_answer":true,"explanation":"one sentence"}]} — worth 1 mark each.'),
        "fillblank": ('Use this shape: {"questions":[{"question":"a sentence with a blank shown as ____",'
                      '"type":"fillblank","correct_answer":"the exact word/phrase that fills the blank",'
                      '"explanation":"one sentence"}]} — worth 1 mark each.'),
        "qa": ('Use this shape: {"questions":[{"question":"...","type":"qa",'
               '"model_answer":"a concise ideal answer (2-4 sentences)","rubric":"2-3 key points a full-marks '
               'answer must cover"}]} — worth 5 marks each.'),
    }
    sys = ("You write exam questions for a corporate training platform, based on the given source material. "
           "Output ONLY valid JSON, no markdown fences, no commentary. "
           f"{type_spec[qtype]} Keep the whole response concise.")
    user_msg = f"Source material:\n{topic_or_context}\n\nGenerate exactly {count} questions of type \"{qtype}\"."
    return ask_claude(sys, user_msg, json_mode=True)["questions"]


# ==================== Learning Path Builder — Day 5 mixed exam ====================
def generate_learning_path_exam(context, formats):
    """formats: dict like {"mcq": {"enabled":True,"questions":5,"timer_min":10}, "fillblank": {...}, "qa": {...}}
    Returns (questions, total_timer_minutes, total_marks)."""
    all_questions = []
    total_timer = 0
    total_marks = 0
    for qtype, cfg in formats.items():
        if not cfg.get("enabled") or not cfg.get("questions"):
            continue
        qs = generate_exam_questions(context, int(cfg["questions"]), qtype)
        for q in qs:
            q["type"] = qtype
            q["timer_min"] = cfg.get("timer_min", 10)
        all_questions.extend(qs)
        total_timer += int(cfg.get("timer_min", 10))
        total_marks += int(cfg["questions"]) * QUESTION_TYPES.get(qtype, ("", 1))[1]
    return all_questions, total_timer, total_marks


def grade_mixed_exam(questions, answers):
    """Grades a per-question-type mixed exam (mcq / truefalse / fillblank auto-graded,
    qa/vshort/short/long AI-graded). Returns (feedback_list, score, max_score)."""
    feedback = [None] * len(questions)
    ai_indices, ai_questions, ai_answers, ai_marks = [], [], [], []

    for i, q in enumerate(questions):
        qtype = q.get("type", "short")
        a = answers.get(i)
        marks = QUESTION_TYPES.get(qtype, ("", 1))[1]
        if qtype == "mcq":
            if a is None:
                feedback[i] = {"score": 0, "feedback": "Not attempted."}
            elif a == q.get("correct_index"):
                feedback[i] = {"score": marks, "feedback": "Correct."}
            else:
                feedback[i] = {"score": 0, "feedback": f"Not quite — {q.get('explanation', 'review this concept.')}"}
        elif qtype == "truefalse":
            if a is None:
                feedback[i] = {"score": 0, "feedback": "Not attempted."}
            elif bool(a) == bool(q.get("correct_answer")):
                feedback[i] = {"score": marks, "feedback": "Correct."}
            else:
                feedback[i] = {"score": 0, "feedback": f"Not quite — {q.get('explanation', 'review this concept.')}"}
        elif qtype == "fillblank":
            correct = str(q.get("correct_answer", "")).strip().lower()
            given = str(a or "").strip().lower()
            if given and (given == correct or correct in given or given in correct):
                feedback[i] = {"score": marks, "feedback": "Correct."}
            else:
                feedback[i] = {"score": 0, "feedback": f"Expected: \"{q.get('correct_answer', '')}\"."}
        else:
            ai_indices.append(i)
            ai_questions.append(q)
            ai_answers.append(a)
            ai_marks.append(marks)

    if ai_questions:
        # group AI questions by mark value so grade_written_answers' shared marks_per_q still makes sense
        for i, q, a, m in zip(ai_indices, ai_questions, ai_answers, ai_marks):
            try:
                single = grade_written_answers([q], {0: a}, m)[0]
            except Exception:
                single = {"score": 0, "feedback": "Could not grade this answer automatically."}
            feedback[i] = single

    score = sum(f["score"] for f in feedback)
    max_score = sum(QUESTION_TYPES.get(q.get("type", "short"), ("", 1))[1] for q in questions)
    return feedback, score, max_score


def grade_written_answers(questions, answers, marks_per_q):
    sys = (f"You are grading exam responses for a training platform. For each item, compare the student's "
           f"answer to the model answer and rubric, then give a score from 0 to {marks_per_q} and one or two "
           f"sentences of specific feedback. "
           f'Output ONLY valid JSON: {{"results":[{{"score":0,"feedback":"..."}}]}} in the same order as given. '
           f"No markdown fences.")
    payload = "\n\n".join(
        f"Q{i+1} (max {marks_per_q} marks): {q['question']}\n"
        f"Model answer: {q['model_answer']}\nRubric: {q['rubric']}\n"
        f"Student answer: {answers.get(i) or '(blank)'}"
        for i, q in enumerate(questions)
    )
    return ask_claude(sys, payload, json_mode=True)["results"]


# ==================== Improvement / gap analysis ====================
def gap_analysis(user_name, exam_title, questions, answers, feedback, score, max_score, sources_context=""):
    sys = (
        "You are an instructional coach for a corporate training platform. Given a trainee's exam questions, "
        "their answers, per-question feedback, and (optionally) relevant training material excerpts, produce a "
        "gap analysis. Output ONLY valid JSON, no markdown fences: "
        '{"key_topics":["...","..."],"likely_gaps":["...","..."],"why":"1-3 sentences explaining the reasoning, '
        'referencing the exam content and score","next_steps":"1-3 sentences of concrete next actions '
        '(e.g. review material, schedule a session, take a remedial quiz)"}'
    )
    qa_block = "\n\n".join(
        f"Q{i+1}: {q['question']}\nStudent answer: {answers.get(i) or '(blank)'}\n"
        f"Feedback: {feedback[i]['feedback']} (score {feedback[i]['score']})"
        for i, q in enumerate(questions)
    )
    user_msg = (f"Trainee: {user_name}\nExam: {exam_title}\nScore: {score}/{max_score}\n\n{qa_block}\n\n"
                f"Relevant training material:\n{sources_context or '(none indexed)'}")
    return ask_claude(sys, user_msg, json_mode=True)


# ==================== Study planner ====================
def generate_study_plan(course_name, topics, duration_weeks, learner_type=None, notes=""):
    """topics: list of topic strings (e.g. document topics for the chosen course).
    Returns {"weeks":[{"week":1,"label":"Week 1","topics":["...","..."]}, ...]}."""
    learner_note = f" The learner's preferred style is: {learner_type}. Bias the pacing and daily focus toward that style." if learner_type else ""
    sys = (
        "You are an academic planner for a training platform. Build a realistic week-by-week study timetable "
        "that spreads the given topics evenly (with light review weeks near the end) across the requested "
        "duration. Break each week into 2-5 concrete topics/subtopics — don't just repeat the input topics "
        "verbatim if a topic is broad, split it into sub-parts across the weeks it needs."
        f"{learner_note} Output ONLY valid JSON, no markdown fences: "
        '{"weeks":[{"week":1,"label":"Week 1","topics":["...","..."]}]} '
        "with exactly the requested number of weeks."
    )
    user_msg = (f"Course: {course_name}\nDuration: {duration_weeks} weeks\n"
                f"Topics to cover: {', '.join(topics) if topics else '(none specified — infer a sensible syllabus for this course)'}\n"
                f"Additional notes: {notes or '(none)'}")
    return ask_claude(sys, user_msg, json_mode=True)["weeks"]


# ==================== Interview prep ====================
def generate_interview_questions(topic, context="", count=8):
    """Returns a list of {"question","model_answer","difficulty"} spanning easy/medium/hard."""
    sys = (
        "You are a senior technical interviewer. Given a topic (and optional source material), write realistic "
        "interview questions a candidate could actually be asked, mixing conceptual, applied, and scenario-based "
        "questions. Spread difficulty roughly evenly across easy/medium/hard. For each, give a strong model answer "
        "(a few sentences, not an essay). Output ONLY valid JSON, no markdown fences: "
        '{"questions":[{"question":"...","model_answer":"...","difficulty":"easy|medium|hard"}]} '
        f"with exactly {count} questions."
    )
    user_msg = f"Topic: {topic}\n" + (f"Source material:\n{context}" if context else "(no source material — use general knowledge of this topic)")
    return ask_claude(sys, user_msg, json_mode=True)["questions"]


def grade_interview_answer(question, model_answer, candidate_answer):
    sys = (
        "You are a supportive but honest mock-interview coach. Compare the candidate's spoken/typed answer to "
        "the model answer and give a score from 0-10 plus two or three sentences of specific, actionable "
        "feedback (what was strong, what to add or fix). Output ONLY valid JSON, no markdown fences: "
        '{"score":0,"feedback":"..."}'
    )
    user_msg = f"Question: {question}\nModel answer: {model_answer}\nCandidate answer: {candidate_answer or '(no answer given)'}"
    return ask_claude(sys, user_msg, json_mode=True)


# ==================== Document summarization ====================
def summarize_document(filename, chunks_text, max_chunks=20):
    sys = ("You summarize training documents for a corporate learning platform. Write a concise summary "
           "(120-180 words) covering what the document teaches and its key points, in plain prose — no headers, "
           "no bullet list, just a clear paragraph a trainee could skim before opening the full document.")
    context = "\n\n".join(chunks_text[:max_chunks])
    return ask_claude(sys, f"Document: {filename}\n\nContent:\n{context}")

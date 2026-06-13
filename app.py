"""
TOEIC Quiz Maker - Web App (Flask)
Chạy: python app.py
Mở trình duyệt: http://localhost:5000
Deploy: Render / Railway (thêm Procfile: web: gunicorn app:app)
"""

import os
import re
import json
import uuid
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import List, Optional, Dict

from flask import Flask, request, jsonify, render_template, session
import google.generativeai as genai

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "toeic-quiz-secret-2024")

STORAGE_DIR = Path.home() / ".toeic_quiz_web" / "quizzes"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# DATA
# ============================================================

@dataclass
class Question:
    id: int
    question_text: str
    options: Dict[str, str]
    correct_answer: str
    user_answer: Optional[str] = None

    def to_dict(self):
        return asdict(self)

    def is_correct(self):
        return self.user_answer == self.correct_answer


# ============================================================
# PARSER
# ============================================================

def parse_quiz(text: str):
    questions, errors = [], []
    for ln, line in enumerate([l.strip() for l in text.split("\n") if l.strip()], 1):
        try:
            if ";" not in line:
                errors.append(f"Dòng {ln}: Thiếu dấu ';'"); continue
            q_part, a_part = line.split(";", 1)
            matches = re.findall(r"\(([A-D])\)\s*([^()]+?)(?=\([A-D]\)|$)", q_part)
            if len(matches) != 4:
                errors.append(f"Dòng {ln}: Cần đúng 4 lựa chọn A-D"); continue
            qs = re.search(r"^\d+\.\s*(.*?)\s*\(", q_part)
            if not qs:
                errors.append(f"Dòng {ln}: Định dạng câu hỏi sai"); continue
            ca = re.search(r"\(([A-D])\)", a_part)
            if not ca:
                errors.append(f"Dòng {ln}: Định dạng đáp án sai"); continue
            questions.append(Question(
                id=len(questions) + 1,
                question_text=qs.group(1).strip(),
                options={k: v.strip() for k, v in matches},
                correct_answer=ca.group(1)
            ))
        except Exception as e:
            errors.append(f"Dòng {ln}: {e}")
    return questions, errors


# ============================================================
# STORAGE
# ============================================================

def save_quiz(title, questions, quiz_id=None):
    qid = quiz_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    path = STORAGE_DIR / f"{qid}.json"
    data = {
        "quiz_id": qid, "title": title,
        "created_date": datetime.now().isoformat(),
        "questions": [q.to_dict() for q in questions]
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return qid


def load_quiz(quiz_id):
    path = STORAGE_DIR / f"{quiz_id}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    qs = [Question(id=q["id"], question_text=q["question_text"],
                   options=q["options"], correct_answer=q["correct_answer"])
          for q in data["questions"]]
    return data["title"], qs


def list_quizzes():
    result = []
    for p in sorted(STORAGE_DIR.glob("*.json"), reverse=True):
        d = json.loads(p.read_text(encoding="utf-8"))
        result.append({"quiz_id": d["quiz_id"], "title": d["title"],
                        "question_count": len(d["questions"]),
                        "created_date": d["created_date"][:10]})
    return result


def delete_quiz(quiz_id):
    p = STORAGE_DIR / f"{quiz_id}.json"
    if p.exists(): p.unlink()


# ============================================================
# AI
# ============================================================

def get_ai_model():
    key = session.get("gemini_key") or os.environ.get("GEMINI_API_KEY", "")
    if not key:
        return None, "Chưa có API key"
    genai.configure(api_key=key)
    model = genai.GenerativeModel(
        "gemini-2.5-flash",
        system_instruction=(
            "Bạn là gia sư TOEIC. "
            "KHÔNG chào hỏi. Đi thẳng vào nội dung. "
            "Luôn trả lời bằng tiếng Việt."
        )
    )
    return model, None


def ai_hint(question_text, options):
    model, err = get_ai_model()
    if err: return f"⚠️ {err}"
    prompt = (f"Gợi ý ngắn (3-4 câu), KHÔNG tiết lộ đáp án:\n\n"
              f"Câu hỏi: {question_text}\n"
              + "\n".join(f"({k}) {v}" for k, v in options.items()))
    try:
        r = model.generate_content(prompt, generation_config=genai.types.GenerationConfig(
            max_output_tokens=512, temperature=0.7))
        return r.text.strip()
    except Exception as e:
        return f"⚠️ Lỗi AI: {str(e)[:120]}"


def ai_explain(question_text, options, correct, user_ans):
    model, err = get_ai_model()
    if err: return f"⚠️ {err}"
    prompt = (f"Giải thích (4-5 câu) tại sao ({correct}) đúng và ({user_ans}) sai. "
              f"Nêu quy tắc ngữ pháp/từ vựng liên quan.\n\n"
              f"Câu hỏi: {question_text}\n"
              + "\n".join(f"({k}) {v}" for k, v in options.items())
              + f"\n\nHọc viên chọn: ({user_ans}) {options.get(user_ans, '')}"
              + f"\nĐáp án đúng: ({correct}) {options.get(correct, '')}")
    try:
        r = model.generate_content(prompt, generation_config=genai.types.GenerationConfig(
            max_output_tokens=512, temperature=0.7))
        return r.text.strip()
    except Exception as e:
        return f"⚠️ Lỗi AI: {str(e)[:120]}"


# ============================================================
# ROUTES
# ============================================================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/set-key", methods=["POST"])
def set_key():
    key = request.json.get("key", "").strip()
    if not key:
        return jsonify({"ok": False, "error": "Key trống"})
    session["gemini_key"] = key
    return jsonify({"ok": True})


@app.route("/api/quizzes")
def api_quizzes():
    return jsonify(list_quizzes())


@app.route("/api/parse", methods=["POST"])
def api_parse():
    text = request.json.get("text", "")
    qs, errors = parse_quiz(text)
    if errors:
        return jsonify({"ok": False, "errors": errors})
    return jsonify({"ok": True, "questions": [q.to_dict() for q in qs]})


@app.route("/api/save", methods=["POST"])
def api_save():
    data = request.json
    title = data.get("title", "Quiz")
    questions = [Question(**{k: q[k] for k in ["id","question_text","options","correct_answer"]})
                 for q in data.get("questions", [])]
    quiz_id = data.get("quiz_id")
    qid = save_quiz(title, questions, quiz_id)
    return jsonify({"ok": True, "quiz_id": qid})


@app.route("/api/load/<quiz_id>")
def api_load(quiz_id):
    try:
        title, qs = load_quiz(quiz_id)
        return jsonify({"ok": True, "title": title, "questions": [q.to_dict() for q in qs]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/delete/<quiz_id>", methods=["DELETE"])
def api_delete(quiz_id):
    delete_quiz(quiz_id)
    return jsonify({"ok": True})


@app.route("/api/hint", methods=["POST"])
def api_hint():
    d = request.json
    return jsonify({"result": ai_hint(d["question_text"], d["options"])})


@app.route("/api/explain", methods=["POST"])
def api_explain():
    d = request.json
    return jsonify({"result": ai_explain(
        d["question_text"], d["options"], d["correct"], d["user_ans"])})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

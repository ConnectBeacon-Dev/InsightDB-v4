from __future__ import annotations

import os
import sys
import json
import time
import re
import random
from pathlib import Path
from flask import (
    Flask, request, jsonify, render_template, Response,
    send_from_directory, abort
)

# Import our query engine
sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine.full_engine_query import EnhancedQueryEngine

# --------------------------------------------------------------------------------------
# Paths & config (override with env vars if you like)
# --------------------------------------------------------------------------------------
APP_DIR = Path(__file__).resolve().parent
BASE_DIR = APP_DIR  # used in a fallback below
TEMPLATES_DIR = APP_DIR / "templates"
STATIC_DIR = APP_DIR / "static"

# Updated paths for new query engine
VIEWS_DIR = Path(os.getenv("VIEWS_DIR", APP_DIR / "views"))
LLM_PATH = Path(os.getenv("LLM_MODEL", "models/Qwen2.5-3B-Instruct-Q8_0.gguf"))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "models/all-MiniLM-L6-v2")
DEFAULT_K = int(os.getenv("RAG_K", "20"))

# Initialize query engine (singleton for the app)
_query_engine = None

def get_query_engine():
    """Get or create the query engine instance"""
    global _query_engine
    if _query_engine is None:
        print(f"Initializing query engine...")
        print(f"  Views: {VIEWS_DIR}")
        print(f"  LLM: {LLM_PATH}")
        _query_engine = EnhancedQueryEngine(
            views_dir=str(VIEWS_DIR),
            model_name=EMBEDDING_MODEL,
            llm_model_path=str(LLM_PATH) if LLM_PATH.exists() else None,
            log_file="query_log.jsonl"
        )
        # Build index on startup
        _query_engine.build_semantic_index(force=False)
        print(" Query engine ready")
    return _query_engine

# =========================== General helpers =========================
_GREET_RE  = re.compile(r"\b(hi|hello|hey|good\s*(morning|afternoon|evening)|namaste)\b", re.I)
_THANKS_RE = re.compile(r"\b(thanks|thank\s*you|much\s*appreciated)\b", re.I)
_BYE_RE    = re.compile(r"\b(bye|goodbye|see\s*you|ttyl|take\s*care)\b", re.I)
_HELP_RE   = re.compile(r"\b(help|how\s*(do|to)|what\s*can\s*you\s*do|examples?)\b", re.I)
_OFFTOPIC_PATTERNS = [
    r"\bweather\b", r"\btemperature\b", r"\brain\b",
    r"\b(date|time)\b", r"\bday\s*is\s*it\b",
    r"\bnews\b", r"\bcricket\b", r"\bfootball\b", r"\bscore\b",
    r"\bmovie\b", r"\bfilm\b", r"\bcelebrity\b",
    r"\bjoke\b", r"\briddle\b", r"\bpoem\b", r"\bstory\b",
    r"\bstock\b", r"\bbitcoin\b", r"\bexchange\s*rate\b"
]
_OFFTOPIC_RE = re.compile("|".join(_OFFTOPIC_PATTERNS), re.I)

_GREETINGS = [
    "Hello!  How can I help you with companies, products, or certifications?",
    "Hi! Ask me about companies (location, domain), ISO certifications, products, or revenue.",
    "Namaste! You can search by certification (e.g., ISO 9001), product (e.g., High Voltage Transformer), or turnover."
]

def _smalltalk_or_offtopic(q: str) -> str | None:
    """Return a short assistant response for smalltalk/help/off-topic, else None."""
    if _GREET_RE.search(q):
        return random.choice(_GREETINGS)
    if _THANKS_RE.search(q):
        return "You're welcome! If you’d like, ask me about company locations, products, or certifications."
    if _BYE_RE.search(q):
        return "Take care!  Come back anytime if you need company details or lists."
    if _HELP_RE.search(q):
        return (
            "I can help you find company details by name, city, state, products, or certifications.\n\n"
            "Examples:\n"
            "• Address of FLONEX OIL TECHNOLOGIES PRIVATE LIMITED\n"
            "• List of companies in Goa\n"
            "• How many companies in Madhya Pradesh\n"
            "• Companies with ISO 9001 in Bengaluru\n"
            "• Products by ‘MMRFIC TECHNOLOGY PRIVATE LIMITED’"
        )
    if _OFFTOPIC_RE.search(q):
        return (
            "I’m focused on company data. Try asking things like:\n"
            "• List of companies in Pune\n"
            "• Address of HEG LIMITED\n"
            "• Companies with ISO 14001 in Telangana"
        )
    return None

# --------------------------------------------------------------------------------------
# Flask app
# --------------------------------------------------------------------------------------
app = Flask(__name__, template_folder=str(TEMPLATES_DIR), static_folder=str(STATIC_DIR))

# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------
def _run_query(question: str, k: int = DEFAULT_K) -> dict:
    """
    Use the integrated query engine instead of CLI subprocess.
    Returns the response dict from natural_language_query.
    """
    engine = get_query_engine()
    response = engine.natural_language_query(question, top_k=k)
    return response

def _find_in(d: Path, filename: str) -> Path:
    p = d / filename
    if p.exists(): return p
    return Path()

def _format_answer(response: dict) -> str:
    """
    Format the query engine response for display.
    Returns formatted text with answer and top results.
    """
    answer = response.get("answer", "No answer generated.")
    results = response.get("results")
    count = response.get("count", 0)
    
    # Simple format - just answer
    output = f"{answer}"
    
    return output

def _sse_token(chunk: str) -> str:
    # chat.html expects event: token with a JSON-encoded string (it does JSON.parse)
    return f"event: token\ndata: {json.dumps(chunk)}\n\n"

def _stream_smalltalk(msg: str):
    """Stream a smalltalk/off-topic reply using the same SSE protocol."""
    CHUNK = 200
    for i in range(0, len(msg), CHUNK):
        yield _sse_token(msg[i:i+CHUNK])
        time.sleep(0.02)
    yield "event: done\ndata: {}\n\n"

# --------------------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------------------
@app.route("/")
def home():
    p = _find_in(TEMPLATES_DIR, "portal.html")
    if p.exists():
        if str(p.parent) == app.template_folder:
            return render_template("portal.html")
        return send_from_directory(p.parent, p.name)
    return "Ask app is running. Put portal.html into ./templates or this folder."

@app.route("/chat")
def chat_page():
    p = _find_in(TEMPLATES_DIR, "index.html")
    if p.exists():
        if str(p.parent) == app.template_folder:
            return render_template("index.html")
        return send_from_directory(p.parent, p.name)
    abort(404, description="index.html not found. Place it under ./templates or alongside the app.")

@app.route("/static/<path:filename>")
def static_fallback(filename: str):
    try:
        return app.send_static_file(filename)
    except Exception:
        pass
    p = _find_in(STATIC_DIR, filename)
    if p.exists():
        return send_from_directory(p.parent, p.name)
    if filename == "askme-modal.js":
        p2 = BASE_DIR / "askme-modal.js"
        if p2.exists():
            return send_from_directory(p2.parent, p2.name)
    abort(404)

@app.post("/ask")
def ask_once():
    """
    Non-streaming variant (returns the whole answer in JSON).
    Handy for quick integrations or debugging.
    """
    data = request.get_json(silent=True) or {}
    q = (data.get("query") or "").strip()
    k = int(data.get("k") or DEFAULT_K)
    if not q:
        return jsonify({"status": "error", "message": "query is required"}), 400

    # Smalltalk/off-topic quick replies (no query engine call)
    st = _smalltalk_or_offtopic(q)
    if st:
        return jsonify({"status": "success", "answer": st})

    try:
        response = _run_query(q, k)
        ans = _format_answer(response)
        return jsonify({"status": "success", "answer": ans})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.post("/ask_stream")
@app.post("/ask_stream/")
def ask_stream():
    """
    Streaming SSE endpoint that chat.html uses.
    Sends event: token chunks and finishes with event: done.
    """
    data = request.get_json(silent=True) or {}
    q = (data.get("query") or "").strip()
    k = int(data.get("k") or DEFAULT_K)

    if not q:
        return Response("event: error\ndata: query is required\n\n", mimetype="text/event-stream")

    # Smalltalk/off-topic quick replies
    st = _smalltalk_or_offtopic(q)
    if st:
        return Response(_stream_smalltalk(st), mimetype="text/event-stream")

    def generate():
        try:
            response = _run_query(q, k)
            ans = _format_answer(response)
            # Stream in small chunks; UI concatenates these (marked.js renders markdown).
            CHUNK = 200
            for i in range(0, len(ans), CHUNK):
                yield _sse_token(ans[i:i+CHUNK])
                time.sleep(0.02)  # tiny delay for smoother UI updates
            yield "event: done\ndata: {}\n\n"
        except Exception as e:
            msg = str(e).replace("\n", " ")
            yield f"event: error\ndata: {json.dumps(msg)}\n\n"

    return Response(generate(), mimetype="text/event-stream")

# --------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=False)

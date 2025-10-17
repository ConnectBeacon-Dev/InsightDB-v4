from __future__ import annotations

import os
import sys
import json
import time
import re
import random
import logging
from pathlib import Path
from datetime import datetime
from flask import (
    Flask, request, jsonify, render_template, Response,
    send_from_directory, abort
)
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

# Import our query engine
sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine.full_engine_query import EnhancedQueryEngine

# --------------------------------------------------------------------------------------
# Logging Setup
# --------------------------------------------------------------------------------------
# Create logs directory if it doesn't exist
LOGS_DIR = Path(__file__).resolve().parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / f'app_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('InsightDB')
logger.info("="*70)
logger.info("InsightDB Application Starting")
logger.info("="*70)

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
# LLM disabled by default (due to CPU compatibility issues)
# Set ENABLE_LLM=1 to enable it
DISABLE_LLM = os.getenv("ENABLE_LLM", "0") != "1"

# Initialize query engine (singleton for the app)
_query_engine = None

def get_query_engine():
    """Get or create the query engine instance"""
    global _query_engine
    if _query_engine is None:
        print(f"Initializing query engine...")
        print(f"  Views: {VIEWS_DIR}")
        
        # Determine LLM path based on DISABLE_LLM flag
        if DISABLE_LLM:
            llm_path = None
            print(f"  LLM: DISABLED by default (set ENABLE_LLM=1 to enable)")
        elif LLM_PATH.exists():
            llm_path = str(LLM_PATH)
            print(f"  LLM: {LLM_PATH}")
        else:
            llm_path = None
            print(f"  LLM: Not found at {LLM_PATH}")
        
        _query_engine = EnhancedQueryEngine(
            views_dir=str(VIEWS_DIR),
            model_name=EMBEDDING_MODEL,
            llm_model_path=None,
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

def _smalltalk_or_offtopic(q: str, user_name: str | None = None) -> str | None:
    """Return a short assistant response for smalltalk/help/off-topic, else None."""
    if _GREET_RE.search(q):
        if user_name:
            return f"Hi {user_name}! " + "Ask me about companies (location, domain), ISO certifications, products, or revenue."
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

# Configure reverse proxy support (handles X-Forwarded-* headers)
# Set x_for=1 to trust 1 proxy (increase if you have multiple proxies)
# Set x_proto=1 to handle X-Forwarded-Proto (http/https)
# Set x_host=1 to handle X-Forwarded-Host
# Set x_prefix=1 to handle X-Forwarded-Prefix (for URL path prefixes)
app.wsgi_app = ProxyFix(
    app.wsgi_app, 
    x_for=int(os.getenv("PROXY_X_FOR", "1")),
    x_proto=int(os.getenv("PROXY_X_PROTO", "1")),
    x_host=int(os.getenv("PROXY_X_HOST", "1")),
    x_prefix=int(os.getenv("PROXY_X_PREFIX", "1"))
)

# Enable CORS for all routes (allows access from file:// and other origins)
CORS(app)

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
@app.route("/aichat/chat")
def chat_page():
    p = _find_in(TEMPLATES_DIR, "index.html")
    if p.exists():
        if str(p.parent) == app.template_folder:
            return render_template("index.html")
        return send_from_directory(p.parent, p.name)
    abort(404, description="index.html not found. Place it under ./templates or alongside the app.")

@app.route("/favicon.ico")
def favicon():
    """Serve favicon at root level (browsers automatically request this)"""
    favicon_path = STATIC_DIR / "favicon.ico"
    if favicon_path.exists():
        return send_from_directory(STATIC_DIR, "favicon.ico", mimetype="image/x-icon")
    abort(404)

@app.route("/static/<path:filename>")
@app.route("/aichat/static/<path:filename>")
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
    user_name = (data.get("user_name") or "").strip() or None
    if not q:
        return jsonify({"status": "error", "message": "query is required"}), 400

    # Smalltalk/off-topic quick replies (no query engine call)
    st = _smalltalk_or_offtopic(q, user_name)
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
@app.post("/aichat/ask_stream")
@app.post("/aichat/ask_stream/")
def ask_stream():
    """
    Streaming SSE endpoint that chat.html uses.
    Sends event: token chunks and finishes with event: done.
    """
    data = request.get_json(silent=True) or {}
    q = (data.get("query") or "").strip()
    k = int(data.get("k") or DEFAULT_K)
    user_name = (data.get("user_name") or "").strip() or None

    if not q:
        logger.warning("Empty query received")
        return Response("event: error\ndata: query is required\n\n", mimetype="text/event-stream")

    logger.info(f"Query received: '{q}' (k={k}, user={user_name or 'anonymous'})")

    # Smalltalk/off-topic quick replies
    st = _smalltalk_or_offtopic(q, user_name)
    if st:
        logger.info(f"Smalltalk response: {st[:50]}...")
        return Response(_stream_smalltalk(st), mimetype="text/event-stream")

    def generate():
        start_time = time.time()
        try:
            response = _run_query(q, k)
            ans = _format_answer(response)
            elapsed = time.time() - start_time
            
            result_count = len(response.get('results', []))
            logger.info(f"Query completed: {result_count} results in {elapsed:.2f}s")
            
            # Stream in small chunks; UI concatenates these (marked.js renders markdown).
            CHUNK = 200
            for i in range(0, len(ans), CHUNK):
                yield _sse_token(ans[i:i+CHUNK])
                time.sleep(0.02)  # tiny delay for smoother UI updates
            yield "event: done\ndata: {}\n\n"
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"Query failed after {elapsed:.2f}s: {str(e)}", exc_info=True)
            msg = str(e).replace("\n", " ")
            yield f"event: error\ndata: {json.dumps(msg)}\n\n"

    return Response(generate(), mimetype="text/event-stream")



def _welcome_message(user_name: str | None = None) -> str:
    base = (
        'Welcome! I can help you find companies by location/domain, ISO certifications, and products. '
        'Try "help" or start with a query like: "electronics manufacturers in India".'
    )
    if user_name:
        return f"Welcome {user_name}! I can help you find companies by location/domain, ISO certifications, and products. " \
               f'Try "help" or start with a query like: "electronics manufacturers in India".'
    return base


@app.route('/welcome', methods=['POST'])
@app.route('/aichat/welcome', methods=['POST'])
def welcome():
    data = request.get_json(silent=True) or {}
    user_name = (data.get('user_name') or '').strip() or None
    msg = _welcome_message(user_name)
    return jsonify({'message': msg})


@app.route('/health', methods=['GET'])
@app.route('/aichat/health', methods=['GET'])
def health_check():
    """
    Health check endpoint showing system status and capabilities.
    Returns JSON with system health, available features, and warnings.
    """
    try:
        engine = get_query_engine()
        
        # Import dependency flags from engine module
        from engine.full_engine_query import (
            TRANSFORMERS_AVAILABLE, HAVE_BM25, INTENT_HANDLER_AVAILABLE, np
        )
        
        # Build status response
        status = {
            "status": "healthy",
            "timestamp": time.time(),
            "capabilities": {
                "semantic_search": TRANSFORMERS_AVAILABLE,
                "keyword_search": True,
                "bm25_scoring": HAVE_BM25,
                "intent_detection": INTENT_HANDLER_AVAILABLE,
                "llm_generation": engine.llm is not None,
                "facility_filtering": True,
                "multi_category_filtering": True
            },
            "dependencies": {
                "numpy": np is not None,
                "pandas": True,  # Always available (critical)
                "sentence_transformers": TRANSFORMERS_AVAILABLE,
                "rank_bm25": HAVE_BM25
            },
            "warnings": [],
            "search_mode": "semantic" if TRANSFORMERS_AVAILABLE else "keyword_fallback"
        }
        
        # Add warnings for missing optional dependencies
        if not TRANSFORMERS_AVAILABLE:
            status["warnings"].append({
                "level": "warning",
                "message": "Semantic search unavailable - using keyword fallback",
                "impact": "Search accuracy may be reduced",
                "fix": "Install sentence-transformers: pip install sentence-transformers"
            })
        
        if not HAVE_BM25:
            status["warnings"].append({
                "level": "info",
                "message": "BM25 scoring unavailable",
                "impact": "Keyword search scoring may be less accurate",
                "fix": "Install rank-bm25: pip install rank-bm25"
            })
        
        if engine.llm is None and not DISABLE_LLM:
            status["warnings"].append({
                "level": "info",
                "message": "LLM generation unavailable",
                "impact": "Using template-based answers instead of LLM-generated",
                "fix": "Check LLM model path or set ENABLE_LLM=1"
            })
        
        # Check data availability
        try:
            views_exist = VIEWS_DIR.exists()
            if views_exist:
                company_file = VIEWS_DIR / "CompanyDetail.csv"
                test_fac_file = VIEWS_DIR / "TestFacilityDetails.csv"
                rd_fac_file = VIEWS_DIR / "RDFacilityDetails.csv"
                
                status["data_files"] = {
                    "company_details": company_file.exists(),
                    "test_facilities": test_fac_file.exists(),
                    "rd_facilities": rd_fac_file.exists()
                }
            else:
                status["warnings"].append({
                    "level": "error",
                    "message": "Views directory not found",
                    "impact": "System cannot function",
                    "fix": f"Ensure {VIEWS_DIR} exists with data files"
                })
                status["status"] = "unhealthy"
        except Exception as e:
            status["warnings"].append({
                "level": "error",
                "message": f"Error checking data files: {str(e)}",
                "impact": "Unknown data availability"
            })
        
        return jsonify(status), 200 if status["status"] == "healthy" else 503
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e),
            "timestamp": time.time()
        }), 500


# --------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=False)

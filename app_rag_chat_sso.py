"""
app_rag_chat_sso.py - Flask RAG Chat with SSO Integration (Production)

Local Dev: Use app_rag_chat.py (no SSO, no Redis)
Production: Use this file (SSO + Redis required)
"""
from __future__ import annotations

import os
import sys
import json
import time
import re
import random
import logging
import hmac
import hashlib
import uuid
import urllib.parse
import yaml
from pathlib import Path
from datetime import datetime
from functools import wraps
from flask import (
    Flask, request, jsonify, render_template, Response,
    send_from_directory, abort, redirect, make_response
)
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
from html import escape

# Import our query engine
sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine.full_engine_query import EnhancedQueryEngine

# --------------------------------------------------------------------------------------
# Load Configuration from YAML
# --------------------------------------------------------------------------------------
APP_DIR = Path(__file__).resolve().parent
CONFIG_FILE = APP_DIR / "config.yaml"

def load_config():
    """Load configuration from YAML file with environment variable overrides."""
    # Load YAML config
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r') as f:
            config = yaml.safe_load(f) or {}
    else:
        print(f"Warning: {CONFIG_FILE} not found, using defaults")
        config = {}
    
    # Helper to get config value with env override
    def get_config(env_key, yaml_path, default=None, convert=None):
        """Get config value: env var > yaml > default"""
        # Check environment variable first
        env_val = os.getenv(env_key)
        if env_val is not None:
            return convert(env_val) if convert else env_val
        
        # Check YAML config
        keys = yaml_path.split('.')
        val = config
        for key in keys:
            if isinstance(val, dict):
                val = val.get(key)
            else:
                val = None
                break
        
        if val is not None:
            return convert(val) if convert else val
        
        return default
    
    # Boolean converter
    def to_bool(val):
        if isinstance(val, bool):
            return val
        return str(val).lower() == "true"
    
    return {
        # URLs
        'LOGIN_URL': get_config('LOGIN_URL', 'urls.login', 'http://localhost:5000'),
        'CHATBOT_URL': get_config('CHATBOT_URL', 'urls.chatbot', 'http://localhost:8000/aichat'),
        
        # SSO Configuration
        'SSO_SECRET': get_config('SSO_SHARED_SECRET', 'sso.secret'),
        'SSO_EXPECT_ISS': get_config('SSO_EXPECT_ISS', 'sso.expect_issuer', 'ddpdashboard-aichatbot-portal'),
        'SSO_EXPECT_AUD': get_config('SSO_EXPECT_AUD', 'sso.expect_audience', 'aichat'),
        'PORTAL_SSO_URL': get_config('PORTAL_SSO_URL', 'sso.portal_url', 'http://127.0.0.1:7000/askme-sso'),
        
        # Cookie Configuration
        'COOKIE_NAME': get_config('COOKIE_NAME', 'cookie.name', 'aichat_sid'),
        'COOKIE_DOMAIN': get_config('COOKIE_DOMAIN', 'cookie.domain'),
        'COOKIE_SECURE': get_config('COOKIE_SECURE', 'cookie.secure', True, to_bool),
        'COOKIE_SAMESITE': get_config('COOKIE_SAMESITE', 'cookie.samesite', 'Lax'),
        'COOKIE_PATH': get_config('COOKIE_PATH', 'cookie.path', '/aichat'),
        
        # Session Configuration
        'SESSION_TTL_IDLE': get_config('SESSION_TTL_IDLE', 'session.ttl_idle', 1800, int),
        'SESSION_TTL_ABS': get_config('SESSION_TTL_ABS', 'session.ttl_absolute', 28800, int),
        
        # Redis Configuration
        'REDIS_URL': get_config('REDIS_URL', 'redis.url', 'redis://127.0.0.1:6379/0'),
        'USE_FAKE_REDIS': get_config('USE_FAKE_REDIS', 'redis.use_fake_redis', True, to_bool),
    }

# Load configuration
config = load_config()

# --------------------------------------------------------------------------------------
# SSO & Session Configuration (PRODUCTION ONLY)
# --------------------------------------------------------------------------------------
SSO_SECRET = config['SSO_SECRET']
if not SSO_SECRET:
    raise RuntimeError("SSO_SHARED_SECRET must be set in config.yaml or as environment variable")

COOKIE_NAME = config['COOKIE_NAME']
COOKIE_DOMAIN = config['COOKIE_DOMAIN']
COOKIE_SECURE = config['COOKIE_SECURE']
COOKIE_SAMESITE = config['COOKIE_SAMESITE']
COOKIE_PATH = config['COOKIE_PATH']

SESSION_TTL_IDLE = config['SESSION_TTL_IDLE']
SESSION_TTL_ABS = config['SESSION_TTL_ABS']

REDIS_URL = config['REDIS_URL']
USE_FAKE_REDIS = config['USE_FAKE_REDIS']
SSO_EXPECT_ISS = config['SSO_EXPECT_ISS']
SSO_EXPECT_AUD = config['SSO_EXPECT_AUD']
PORTAL_SSO_URL = config['PORTAL_SSO_URL']

# Initialize Redis (PRODUCTION - Supports both real Redis and fakeredis)
try:
    if USE_FAKE_REDIS:
        import fakeredis
        r = fakeredis.FakeStrictRedis(decode_responses=True)
        print(f"[OK] Using fakeredis (in-memory) - suitable for restrictive environments")
    else:
        import redis
        r = redis.from_url(REDIS_URL, decode_responses=True)
        r.ping()  # Verify connection
        print(f"[OK] Connected to Redis at {REDIS_URL}")
except ImportError as ie:
    if USE_FAKE_REDIS:
        raise RuntimeError("fakeredis package not installed. Run: pip install fakeredis")
    else:
        raise RuntimeError("redis package not installed. Run: pip install redis")
except Exception as e:
    if not USE_FAKE_REDIS:
        raise RuntimeError(f"Failed to connect to Redis at {REDIS_URL}: {e}")
    else:
        raise

# Import JWT for SSO
try:
    import jwt
except ImportError:
    raise RuntimeError("PyJWT not installed. Run: pip install PyJWT")

# --------------------------------------------------------------------------------------
# Logging Setup
# --------------------------------------------------------------------------------------
LOGS_DIR = Path(__file__).resolve().parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

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
logger.info("InsightDB Application Starting (PRODUCTION - SSO Enabled)")
logger.info("="*70)

# --------------------------------------------------------------------------------------
# Paths & config
# --------------------------------------------------------------------------------------
# APP_DIR already defined above during config loading
TEMPLATES_DIR = APP_DIR / "templates"
STATIC_DIR = APP_DIR / "static"

VIEWS_DIR = Path(os.getenv("VIEWS_DIR", APP_DIR / "views"))
LLM_PATH = Path(os.getenv("LLM_MODEL", "models/Qwen2.5-3B-Instruct-Q8_0.gguf"))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "models/all-MiniLM-L6-v2")
DEFAULT_K = int(os.getenv("RAG_K", "20"))
DISABLE_LLM = os.getenv("ENABLE_LLM", "0") != "1"

# --------------------------------------------------------------------------------------
# Flask App Setup
# --------------------------------------------------------------------------------------
app = Flask(__name__, template_folder=str(TEMPLATES_DIR), static_folder=str(STATIC_DIR))
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
CORS(app)

# --------------------------------------------------------------------------------------
# SSO Session Management Functions
# --------------------------------------------------------------------------------------
def now(): 
    return int(time.time())

def hmac_ok(sig, body):
    """Verify HMAC signature for backchannel requests."""
    mac = hmac.new(SSO_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest((sig or "").lower(), mac.lower())

def verify_jwt(tok: str) -> dict:
    """Verify JWT token from SSO portal."""
    return jwt.decode(tok, SSO_SECRET, algorithms=["HS256"],
                      audience=SSO_EXPECT_AUD,
                      issuer=SSO_EXPECT_ISS,
                      options={"require": ["exp", "iss", "aud", "sub"]}, leeway=5)

def sess_key(sid): return f"sess:{sid}"
def user_set(uid): return f"user:{uid}:sids"
def user_rev(uid): return f"user:{uid}:revoked_at"

def create_session(uid, claims) -> str:
    """Create new session in Redis."""
    sid = str(uuid.uuid4())
    t = now()
    pipe = r.pipeline()
    pipe.hset(sess_key(sid), mapping={
        "uid": uid,
        "iat": str(t),
        "last": str(t),
        "claims": json.dumps(claims)
    })
    pipe.expire(sess_key(sid), SESSION_TTL_IDLE)
    pipe.sadd(user_set(uid), sid)
    pipe.execute()
    logger.info(f"Session created: user={uid}, session={sid}")
    return sid

def destroy_session(sid):
    """Destroy session in Redis."""
    data = r.hgetall(sess_key(sid))
    if data:
        r.srem(user_set(data.get("uid", "")), sid)
        logger.info(f"Session destroyed: session={sid}, user={data.get('uid')}")
    r.delete(sess_key(sid))

def revoke_all(uid):
    """Revoke all sessions for a user (backchannel logout)."""
    r.set(user_rev(uid), now())
    for sid in r.smembers(user_set(uid)):
        destroy_session(sid)
    r.delete(user_set(uid))
    logger.info(f"All sessions revoked for user={uid}")

def get_session(req):
    """Get and validate session from request cookies."""
    sid = req.cookies.get(COOKIE_NAME)
    if not sid:
        return None, None
    
    data = r.hgetall(sess_key(sid))
    if not data:
        return None, sid
    
    iat = int(data.get("iat", "0"))
    t = now()
    
    # Check absolute timeout
    if iat + SESSION_TTL_ABS < t:
        destroy_session(sid)
        logger.warning(f"Session expired (absolute timeout): session={sid}")
        return None, sid
    
    # Check revocation
    rev = r.get(user_rev(data.get("uid")))
    if rev and int(rev) >= iat:
        destroy_session(sid)
        logger.warning(f"Session revoked: session={sid}")
        return None, sid
    
    # Renew idle timeout
    r.expire(sess_key(sid), SESSION_TTL_IDLE)
    r.hset(sess_key(sid), "last", t)
    
    try:
        data["claims"] = json.loads(data.get("claims") or "{}")
    except:
        data["claims"] = {}
    
    return data, sid

def set_cookie(resp, sid):
    """Set session cookie."""
    resp.set_cookie(
        COOKIE_NAME, sid,
        max_age=SESSION_TTL_IDLE,
        secure=COOKIE_SECURE,
        httponly=True,
        samesite=COOKIE_SAMESITE,
        domain=COOKIE_DOMAIN,
        path=COOKIE_PATH
    )

def del_cookie(resp):
    """Delete session cookie."""
    resp.delete_cookie(COOKIE_NAME, domain=COOKIE_DOMAIN, path=COOKIE_PATH)

# --------------------------------------------------------------------------------------
# Authentication Decorator
# --------------------------------------------------------------------------------------
def require_auth(f):
    """Decorator to require authentication for routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        sess, _ = get_session(request)
        if not sess:
            # Session expired or missing - redirect to SSO
            if PORTAL_SSO_URL and request.path.startswith('/aichat/'):
                ret = urllib.parse.quote(request.path, safe="")
                logger.info(f"Redirecting to SSO: {request.path}")
                return redirect(f"{PORTAL_SSO_URL}?return={ret}")
            return jsonify({"error": "Authentication required"}), 401
        
        # Store session in request context for use in route
        request.session_data = sess
        return f(*args, **kwargs)
    
    return decorated_function

# --------------------------------------------------------------------------------------
# Query Engine Singleton
# --------------------------------------------------------------------------------------
_query_engine = None

def get_query_engine():
    """Get or create the query engine instance"""
    global _query_engine
    if _query_engine is None:
        logger.info(f"Initializing query engine...")
        logger.info(f"  Views: {VIEWS_DIR}")
        
        if DISABLE_LLM:
            llm_path = None
            logger.info(f"  LLM: Disabled")
        else:
            llm_path = str(LLM_PATH) if LLM_PATH.exists() else None
            if llm_path:
                logger.info(f"  LLM: {LLM_PATH}")
            else:
                logger.info(f"  LLM: Not found at {LLM_PATH}")
        
        _query_engine = EnhancedQueryEngine(
            views_dir=str(VIEWS_DIR),
            model_name=EMBEDDING_MODEL,
            llm_model_path=llm_path,
            log_file="query_log.jsonl"
        )
        # Build index on startup
        _query_engine.build_semantic_index(force=False)
        logger.info("[OK] Query engine ready")
    return _query_engine

# --------------------------------------------------------------------------------------
# SSO Routes
# --------------------------------------------------------------------------------------
@app.route('/aichat/sso')
def sso():
    """SSO callback endpoint - receives JWT token from portal."""
    token = request.args.get('token')
    ret = request.args.get('ret', '/aichat/')
    
    if not token:
        logger.error("SSO callback missing token")
        return jsonify({"error": "Token required"}), 400
    
    try:
        claims = verify_jwt(token)
        uid = claims["sub"]
        
        resp = make_response(redirect(ret))
        set_cookie(resp, create_session(uid, claims))
        
        logger.info(f"SSO login successful: user={uid}, name={claims.get('name')}")
        return resp
    except jwt.ExpiredSignatureError:
        logger.error("SSO token expired")
        return jsonify({"error": "Token expired"}), 401
    except jwt.InvalidTokenError as e:
        logger.error(f"SSO token invalid: {e}")
        return jsonify({"error": "Invalid token"}), 401
    except Exception as e:
        logger.error(f"SSO verification failed: {e}", exc_info=True)
        return jsonify({"error": "Authentication failed"}), 500

@app.route('/aichat/logout', methods=['POST'])
@require_auth
def logout():
    """Logout endpoint - destroys session."""
    _, sid = get_session(request)
    resp = make_response('', 204)
    
    if sid:
        destroy_session(sid)
        del_cookie(resp)
    
    return resp

@app.route('/aichat/backchannel_logout', methods=['POST'])
def backchannel_logout():
    """Backchannel logout - called by portal to revoke all user sessions."""
    body = request.get_data()
    
    # Verify HMAC signature
    if not hmac_ok(request.headers.get("X-Signature"), body):
        logger.error("Backchannel logout: Invalid signature")
        return jsonify({"error": "Invalid signature"}), 401
    
    try:
        data = json.loads(body.decode() or "{}")
        uid = data.get("user_id")
        
        if not uid:
            return jsonify({"error": "user_id required"}), 400
        
        revoke_all(uid)
        return jsonify({"ok": True})
    except Exception as e:
        logger.error(f"Backchannel logout failed: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

# --------------------------------------------------------------------------------------
# Main Chat Routes
# --------------------------------------------------------------------------------------
@app.route('/')
@app.route('/aichat/')
@require_auth
def chat():
    """Main chat interface - requires authentication."""
    sess = request.session_data
    user_name = sess["claims"].get("name") or sess["uid"]
    
    # Get login URL for logout redirect
    login_url = os.getenv('LOGIN_URL', PORTAL_SSO_URL or 'http://localhost:5000')
    
    return render_template('chat.html', user_name=user_name, sso_enabled=True, login_url=login_url)

@app.route('/static/<path:filename>')
def serve_static(filename):
    """Serve static files."""
    return send_from_directory(STATIC_DIR, filename)

# --------------------------------------------------------------------------------------
# Query Routes
# --------------------------------------------------------------------------------------
def _run_query(question: str, k: int = DEFAULT_K):
    """Run query through the engine."""
    engine = get_query_engine()
    return engine.natural_language_query(question, top_k=k)

def _format_answer(response: dict) -> str:
    """Format the query engine response for display."""
    answer = response.get("answer", "No answer generated.")
    return f"{answer}"

def _sse_token(chunk: str) -> str:
    return f"event: token\ndata: {json.dumps(chunk)}\n\n"

@app.post("/ask_stream/")
@app.post("/aichat/ask_stream")
@app.post("/aichat/ask_stream/")
@require_auth
def ask_stream():
    """Streaming SSE endpoint - requires authentication."""
    data = request.get_json(silent=True) or {}
    q = (data.get("query") or "").strip()
    k = int(data.get("k") or DEFAULT_K)
    
    sess = request.session_data
    user_name = sess["claims"].get("name") or sess["uid"]
    
    if not q:
        logger.warning(f"Empty query from user={user_name}")
        return Response("event: error\ndata: query is required\n\n", mimetype="text/event-stream")
    
    logger.info(f"Query: '{q}' (k={k}, user={user_name})")
    
    def generate():
        start_time = time.time()
        try:
            response = _run_query(q, k)
            ans = _format_answer(response)
            elapsed = time.time() - start_time
            
            result_count = len(response.get('results', []))
            logger.info(f"Query completed: {result_count} results in {elapsed:.2f}s (user={user_name})")
            
            # Stream in small chunks
            CHUNK = 200
            for i in range(0, len(ans), CHUNK):
                yield _sse_token(ans[i:i+CHUNK])
                time.sleep(0.02)
            yield "event: done\ndata: {}\n\n"
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"Query failed after {elapsed:.2f}s (user={user_name}): {str(e)}", exc_info=True)
            msg = str(e).replace("\n", " ")
            yield f"event: error\ndata: {json.dumps(msg)}\n\n"
    
    return Response(generate(), mimetype="text/event-stream")

@app.route('/health', methods=['GET'])
@app.route('/aichat/health', methods=['GET'])
def health_check():
    """Health check endpoint - no authentication required."""
    try:
        engine = get_query_engine()
        
        from engine.full_engine_query import (
            TRANSFORMERS_AVAILABLE, HAVE_BM25, INTENT_HANDLER_AVAILABLE, np
        )
        
        # Check Redis connection
        redis_ok = False
        redis_type = "fakeredis" if USE_FAKE_REDIS else "real"
        try:
            if USE_FAKE_REDIS:
                redis_ok = True  # fakeredis is always available if initialized
            else:
                r.ping()
                redis_ok = True
        except:
            pass
        
        status = {
            "status": "healthy" if redis_ok else "degraded",
            "timestamp": time.time(),
            "sso_enabled": True,
            "redis_connected": redis_ok,
            "redis_type": redis_type,
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
                "pandas": True,
                "sentence_transformers": TRANSFORMERS_AVAILABLE,
                "rank_bm25": HAVE_BM25,
                "redis": redis_ok,
                "redis_type": redis_type
            },
            "warnings": [],
            "search_mode": "semantic" if TRANSFORMERS_AVAILABLE else "keyword_fallback"
        }
        
        if not redis_ok:
            status["warnings"].append({
                "level": "error",
                "message": "Redis connection failed",
                "impact": "Sessions will not work",
                "fix": "Check Redis server is running"
            })
        
        if not TRANSFORMERS_AVAILABLE:
            status["warnings"].append({
                "level": "warning",
                "message": "Semantic search unavailable - using keyword fallback",
                "impact": "Search accuracy may be reduced",
                "fix": "Install sentence-transformers: pip install sentence-transformers"
            })
        
        return jsonify(status), 200 if redis_ok else 503
        
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
    logger.info(f"Starting PRODUCTION server on port {port}")
    logger.info(f"SSO: Enabled (required)")
    if USE_FAKE_REDIS:
        logger.info(f"Redis: fakeredis (in-memory)")
    else:
        logger.info(f"Redis: {REDIS_URL}")
    logger.info(f"Portal SSO URL: {PORTAL_SSO_URL}")
    app.run(host="0.0.0.0", port=port, debug=False)

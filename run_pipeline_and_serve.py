#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import os

# Fix encoding for Windows console (must be before any other imports that might print)
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    os.environ['PYTHONIOENCODING'] = 'utf-8'

"""
run_pipeline_and_serve.py

Production-grade offline launcher that:
  1) Ensures waitress is installed from wheelhouse (no internet)
  2) Runs ETL and indexing
  3) (optional) Smoke query
  4) Starts LOGIN SERVER (app_simple_login:app) on port 5000 with waitress
  5) Starts CHATBOT SERVER (app_rag_chat_sso:app) on port 8000 with waitress
  6) ALWAYS enables reverse proxy support (PROXY_X_* environment variables)
  7) Runs both servers in background with proper process management
Works even if .venv is not activated.

Environment Variables:
  SERVER_HOST - Server bind IP address (default: 0.0.0.0)
                Example in PowerShell: $env:SERVER_HOST="192.168.1.100"; python run_pipeline_and_serve.py
  SSO_SHARED_SECRET - Required for SSO mode (MUST be set)

Usage Examples:

Minimal (uses all defaults, SSO enabled by default):
  $env:SSO_SHARED_SECRET="test-secret-for-development1"; python run_pipeline_and_serve.py

Without SSO (no authentication, single server):
  python run_pipeline_and_serve.py --no-sso

With custom ports:
  $env:SSO_SHARED_SECRET="your-secret"; python run_pipeline_and_serve.py --port 9000 --login-port 6000

Skip ETL and run in background with SSO:
  $env:SSO_SHARED_SECRET="your-secret"; python run_pipeline_and_serve.py --skip-etl --detached

Custom threads for each server:
  $env:SSO_SHARED_SECRET="your-secret"; python run_pipeline_and_serve.py --threads 16 --login-threads 8

Full custom (PowerShell/CMD):
  $env:SSO_SHARED_SECRET="your-secret"; python run_pipeline_and_serve.py ^
    --port 8000 --login-port 5000 --threads 8 --login-threads 4 --detached

Defaults:
  --wheelhouse wheelhouse
  --venv .venv
  --inputs inputs
  --views views
  --models-dir models
  --model-gguf models/Qwen2.5-3B-Instruct-Q8_0.gguf
  --embedding-model models/all-MiniLM-L6-v2
  --port 8000 (chatbot)
  --login-port 5000 (login server)
  --threads 8 (chatbot)
  --login-threads 4 (login server)
  --tmp-dir .tmp
  SERVER_HOST 0.0.0.0 (environment variable)

Quick Start:
  1. Set secret: $env:SSO_SHARED_SECRET="test-secret-for-development1"
  2. Run: python run_pipeline_and_serve.py
  3. Open: http://localhost:5000
  4. Login and chat!
"""


import argparse
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent

def venv_python_path(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

def venv_pip_path(venv: Path) -> Path:
    return venv / ("Scripts/pip.exe" if os.name == "nt" else "bin/pip")

def mkdir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p

def set_repo_local_temp_and_caches(tmp_dir: Path | None) -> None:
    base = mkdir(tmp_dir or (REPO / ".tmp"))
    os.environ.setdefault("TEMP", str(base))
    os.environ.setdefault("TMP", str(base))
    os.environ.setdefault("TMPDIR", str(base))
    os.environ.setdefault("PIP_CACHE_DIR", str(mkdir(REPO / ".pip_cache")))
    os.environ.setdefault("HF_HOME", str(mkdir(REPO / ".hf_home")))
    os.environ.setdefault("TRANSFORMERS_CACHE", str(mkdir(REPO / ".hf_cache")))
    os.environ.setdefault("TORCH_HOME", str(mkdir(REPO / ".torch_home")))
    os.environ.setdefault("PIP_NO_INPUT", "1")
    os.environ.setdefault("PIP_DISABLE_PIP_VERSION_CHECK", "1")

def run(cmd: list[str], cwd: Path | None = None, env: dict | None = None, check: bool = True) -> None:
    print(f"\n[RUN] {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env, check=check)

def install_waitress_offline(pip_exe: Path, wheelhouse: Path) -> None:
    print("[PKG] Installing waitress from wheelhouse (offline)…")
    env = os.environ.copy()
    env["PIP_NO_INDEX"] = "1"
    run([str(pip_exe), "install", "--no-index", f"--find-links={wheelhouse}", "waitress"], env=env)

def run_etl_and_index(py: Path, inputs: Path, views: Path) -> None:
    mkdir(views)
    run([str(py), str(REPO / "etl" / "build_views_pandas.py"), "--inputs", str(inputs), "--views", str(views)])
    run([str(py), str(REPO / "engine" / "full_engine_query.py"), "index", "--views", str(views), "--force"])

def smoke_query(py: Path, views: Path, ask: str, topk: int) -> None:
    run([str(py), str(REPO / "engine" / "full_engine_query.py"), "query", "--views", str(views),
         "--ask", ask, "--top-k", str(topk)], check=False)

def start_login_server(py: Path, host: str, port: int, threads: int, env: dict, detached: bool, log_dir: Path | None) -> subprocess.Popen | None:
    """Start the login server with waitress (production-grade)"""
    cmd = [str(py), "-m", "waitress", "--listen", f"{host}:{port}", "--threads", str(threads), "app_simple_login:app"]
    login_env = env.copy()
    login_env["LOGIN_PORT"] = str(port)
    
    print(f"[LOGIN] Starting login server on {host}:{port} (threads={threads})")
    
    mkdir(log_dir or (REPO / "logs"))
    log_file = (log_dir or (REPO / "logs")) / "login_server.out"
    stdout = open(log_file, "ab", buffering=0)
    stderr = stdout
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS  # type: ignore[attr-defined]
    
    proc = subprocess.Popen(cmd, env=login_env, cwd=str(REPO),
                            stdout=stdout, stderr=stderr,
                            creationflags=creationflags, close_fds=(os.name != "nt"))
    print(f"[LOGIN] Detached PID = {proc.pid}")
    print(f"[LOG]   {log_file}")
    
    # Give it a moment to start
    time.sleep(2)
    
    # Check if process is still running
    if proc.poll() is not None:
        print(f"[ERROR] Login server failed to start (exit code: {proc.returncode})")
        print(f"[ERROR] Check log file: {log_file}")
        return None
    
    return proc

def start_waitress(py: Path, host: str, port: int, threads: int, env: dict, detached: bool, log_dir: Path | None, use_sso: bool = False) -> subprocess.Popen | None:
    app_module = "app_rag_chat_sso:app" if use_sso else "app_rag_chat:app"
    cmd = [str(py), "-m", "waitress", "--listen", f"{host}:{port}", "--threads", str(threads), app_module]
    print(f"[SERVE] Starting chatbot on {host}:{port} (threads={threads})")
    print(f"[SERVE] Application: {app_module} {'(SSO enabled)' if use_sso else '(no authentication)'}")

    if detached:
        # background with log redirection
        mkdir(log_dir or (REPO / "logs"))
        log_file = (log_dir or (REPO / "logs")) / "chatbot_server.out"
        # open file handles and detach process (Windows & POSIX)
        stdout = open(log_file, "ab", buffering=0)
        stderr = stdout
        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS  # type: ignore[attr-defined]
        proc = subprocess.Popen(cmd, env=env, cwd=str(REPO),
                                stdout=stdout, stderr=stderr,
                                creationflags=creationflags, close_fds=(os.name != "nt"))
        print(f"[SERVE] Detached PID = {proc.pid}")
        print(f"[LOG]   {log_file}")
        
        # Give it a moment to start
        time.sleep(2)
        
        # Check if process is still running
        if proc.poll() is not None:
            print(f"[ERROR] Chatbot server failed to start (exit code: {proc.returncode})")
            print(f"[ERROR] Check log file: {log_file}")
            return None
        
        return proc
    else:
        # foreground (blocking)
        run(cmd, cwd=REPO, env=env, check=True)
        return None

def main():
    ap = argparse.ArgumentParser(
        description="Run ETL->index->serve via Waitress (offline + no venv activation).",
        epilog="Minimal usage: python run_pipeline_and_serve.py (uses all defaults)"
    )
    ap.add_argument("--wheelhouse", type=Path, default=Path("wheelhouse"), 
                   help="Wheelhouse directory (default: ./wheelhouse)")
    ap.add_argument("--venv", type=Path, default=Path(".venv"), 
                   help="Virtualenv directory (default: ./.venv)")
    ap.add_argument("--inputs", type=Path, default=Path("inputs"), 
                   help="ETL inputs folder (default: ./inputs)")
    ap.add_argument("--views", type=Path, default=Path("views"), 
                   help="Views output folder (default: ./views)")
    ap.add_argument("--models-dir", type=Path, default=Path("models"), 
                   help="Models root directory (default: ./models)")
    ap.add_argument("--model-gguf", type=Path, default=Path("models/Qwen2.5-3B-Instruct-Q8_0.gguf"), 
                   help="Path to Qwen GGUF file (default: models/Qwen2.5-3B-Instruct-Q8_0.gguf)")
    ap.add_argument("--embedding-model", type=Path, default=Path("models/all-MiniLM-L6-v2"), 
                   help="Sentence-transformers model folder (default: models/all-MiniLM-L6-v2)")
    ap.add_argument("--port", type=int, default=8000, 
                   help="Chatbot server port (default: 8000)")
    ap.add_argument("--login-port", type=int, default=5000,
                   help="Login server port (default: 5000)")
    ap.add_argument("--threads", type=int, default=8, 
                   help="Waitress threads (default: 8)")
    ap.add_argument("--login-threads", type=int, default=4,
                   help="Login server threads (default: 4)")
    ap.add_argument("--tmp-dir", type=Path, default=Path(".tmp"), 
                   help="Repo-local temp dir (default: ./.tmp)")
    ap.add_argument("--detached", action="store_true", default=True,
                   help="Run waitress in background (always enabled by default)")
    ap.add_argument("--skip-etl", action="store_true", 
                   help="Skip ETL build_views_pandas.py")
    ap.add_argument("--skip-index", action="store_true", 
                   help="Skip index build")
    ap.add_argument("--smoke-ask", default='hello', 
                   help="Smoke query question (default: 'hello')")
    ap.add_argument("--smoke-topk", type=int, default=3, 
                   help="Smoke query top-k (default: 3)")
    ap.add_argument("--sso", action="store_true", default=True,
                   help="Use app_rag_chat_sso.py (SSO-enabled) instead of app_rag_chat.py (default: True)")
    ap.add_argument("--no-sso", action="store_false", dest="sso",
                   help="Disable SSO and use app_rag_chat.py (no authentication)")
    ap.add_argument("--config", type=Path, default=Path("config.yaml"),
                   help="Path to config.yaml for SSO mode (default: ./config.yaml)")
    args = ap.parse_args()

    # force local temp/caches so nothing writes to C:\
    set_repo_local_temp_and_caches(args.tmp_dir)

    # SSO mode validation
    if args.sso:
        print("[CONFIG] SSO mode enabled")
        if not args.config.exists():
            print(f"[WARN] config.yaml not found at {args.config}")
            print("[WARN] Make sure config.yaml exists or SSO app will fail to start")
        
        # Check for SSO_SHARED_SECRET
        if not os.environ.get("SSO_SHARED_SECRET"):
            print("[WARN] SSO_SHARED_SECRET environment variable not set")
            print("[WARN] Set it with: $env:SSO_SHARED_SECRET='your-secret' (PowerShell)")
            print("[WARN] Or the SSO app will fail to start")
    else:
        print("[CONFIG] SSO mode disabled (using app_rag_chat.py)")

    # venv executables (no activation required)
    py = venv_python_path(args.venv.resolve())
    pip = venv_pip_path(args.venv.resolve())
    if not py.exists() or not pip.exists():
        raise SystemExit(f"[ERROR] venv not found or incomplete at {args.venv}. Run your offline installer first.")

    # offline waitress install
    install_waitress_offline(pip, args.wheelhouse.resolve())

    # run ETL + index
    if not args.skip_etl:
        run_etl_and_index(py, args.inputs.resolve(), args.views.resolve())
    elif not args.skip_index:
        # if skipping ETL but not index, still ensure views dir exists
        mkdir(args.views.resolve())

    if not args.skip_index:
        run([str(py), str(REPO / "engine" / "full_engine_query.py"), "index", "--views", str(args.views.resolve()), "--force"])

    # quick smoke query (non-fatal)
    smoke_query(py, args.views.resolve(), args.smoke_ask, args.smoke_topk)

    # Get server host from environment variable or use default
    server_host = os.environ.get("SERVER_HOST", "0.0.0.0")
    print(f"[CONFIG] Server host: {server_host} (from {'SERVER_HOST env var' if 'SERVER_HOST' in os.environ else 'default'})")

    # runtime env for the app
    app_env = os.environ.copy()
    app_env.setdefault("TRANSFORMERS_OFFLINE", "1")
    app_env.setdefault("HF_HUB_OFFLINE", "1")
    app_env["PORT"] = str(args.port)
    app_env["VIEWS_DIR"] = str(args.views.resolve())
    app_env["LLM_MODEL"] = str(args.model_gguf.resolve())
    app_env["EMBEDDING_MODEL"] = str(args.embedding_model.resolve())
    
    # SSO-specific environment (if enabled)
    if args.sso:
        # SSO_SHARED_SECRET should already be in environment
        # Just ensure config path is accessible
        if args.config.exists():
            print(f"[CONFIG] Using config file: {args.config}")
        # Note: app_rag_chat_sso.py will load config.yaml from current directory
    
    # Reverse proxy support - ALWAYS ENABLED
    # These control how Flask handles X-Forwarded-* headers from reverse proxies
    # Always trust 1 proxy for each header type
    app_env["PROXY_X_FOR"] = "1"      # X-Forwarded-For (client IP)
    app_env["PROXY_X_PROTO"] = "1"    # X-Forwarded-Proto (http/https)
    app_env["PROXY_X_HOST"] = "1"     # X-Forwarded-Host (hostname)
    app_env["PROXY_X_PREFIX"] = "1"   # X-Forwarded-Prefix (URL prefix)

    # Start login server first (if SSO enabled)
    login_proc = None
    if args.sso:
        print("\n" + "="*70)
        print("STARTING LOGIN SERVER")
        print("="*70)
        login_proc = start_login_server(py, server_host, args.login_port, args.login_threads, 
                                       app_env, args.detached, log_dir=REPO / "logs")
        if not login_proc:
            print("[ERROR] Failed to start login server. Aborting.")
            sys.exit(1)
        print(f"[OK] Login server running on port {args.login_port}")
    
    # Start chatbot server
    print("\n" + "="*70)
    print("STARTING CHATBOT SERVER")
    print("="*70)
    chatbot_proc = start_waitress(py, server_host, args.port, args.threads, app_env, 
                                  args.detached, log_dir=REPO / "logs", use_sso=args.sso)
    
    if args.detached and not chatbot_proc:
        print("[ERROR] Failed to start chatbot server.")
        # Kill login server if it was started
        if login_proc:
            print("[CLEANUP] Stopping login server...")
            login_proc.terminate()
        sys.exit(1)
    
    print(f"[OK] Chatbot server running on port {args.port}")

    print("\n" + "="*70)
    print("=== ALL SERVICES READY ===")
    print("="*70)
    
    # Show accessible URLs
    if server_host == "0.0.0.0":
        print("\nServers listening on all interfaces (0.0.0.0)")
        print("\n📍 Access URLs:")
        
        if args.sso:
            print(f"\n  🔐 LOGIN PAGE (Start here):")
            print(f"     Local:   http://127.0.0.1:{args.login_port}/")
            print(f"     Local:   http://localhost:{args.login_port}/")
            
            print(f"\n  💬 CHATBOT (after login):")
            print(f"     Local:   http://127.0.0.1:{args.port}/aichat/")
            print(f"     Local:   http://localhost:{args.port}/aichat/")
        else:
            print(f"\n  💬 CHATBOT:")
            print(f"     Local:   http://127.0.0.1:{args.port}/")
            print(f"     Local:   http://localhost:{args.port}/")
        
        # Try to get actual IP
        import socket
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            if local_ip and local_ip != "127.0.0.1":
                if args.sso:
                    print(f"\n  🌐 Network Access:")
                    print(f"     Login:   http://{local_ip}:{args.login_port}/")
                    print(f"     Chatbot: http://{local_ip}:{args.port}/aichat/")
                else:
                    print(f"\n  🌐 Network: http://{local_ip}:{args.port}/")
        except:
            pass
    else:
        if args.sso:
            print(f"\n  🔐 Login:   http://{server_host}:{args.login_port}/")
            print(f"  💬 Chatbot: http://{server_host}:{args.port}/aichat/")
        else:
            print(f"\n  💬 Chatbot: http://{server_host}:{args.port}/")
    
    if args.sso:
        print(f"\n📋 Quick Start:")
        print(f"   1. Open: http://localhost:{args.login_port}/")
        print(f"   2. Enter your details (User ID, Name, Email)")
        print(f"   3. Click 'Continue to Chatbot'")
        print(f"   4. Start chatting!")
        print(f"\n🔍 Health check (no auth): http://127.0.0.1:{args.port}/aichat/health")
    
    if args.detached:
        print("\n📝 Log Files:")
        if args.sso:
            print(f"   Login:   logs/login_server.out")
        print(f"   Chatbot: logs/chatbot_server.out")
        print("\n✅ All servers running in background")
        
        # Save PIDs for later management
        pid_file = REPO / "logs" / "server.pids"
        with open(pid_file, "w") as f:
            if login_proc:
                f.write(f"LOGIN_PID={login_proc.pid}\n")
            if chatbot_proc:
                f.write(f"CHATBOT_PID={chatbot_proc.pid}\n")
        print(f"   PIDs saved to: {pid_file}")

if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Command failed with exit code {e.returncode}")
        sys.exit(e.returncode)
    except SystemExit as e:
        print(e)
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)

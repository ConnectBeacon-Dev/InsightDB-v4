#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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

Offline-friendly launcher that:
  1) Ensures waitress is installed from wheelhouse (no internet)
  2) Runs ETL and indexing
  3) (optional) Smoke query
  4) Serves app_rag_chat:app with waitress on 0.0.0.0:PORT
Works even if .venv is not activated.

Usage Examples:

Minimal (uses all defaults):
  python run_pipeline_and_serve.py

With custom port and detached mode:
  python run_pipeline_and_serve.py --port 9000 --detached

Skip ETL and run in background:
  python run_pipeline_and_serve.py --skip-etl --detached

Full custom (PowerShell/CMD):
  python run_pipeline_and_serve.py --wheelhouse wheelhouse --venv .venv --inputs inputs --views views ^
    --model-gguf models\\Qwen2.5-3B-Instruct-Q8_0.gguf --port 8000 --threads 8 --detached

Defaults:
  --wheelhouse wheelhouse
  --venv .venv
  --inputs inputs
  --views views
  --models-dir models
  --model-gguf models/Qwen2.5-3B-Instruct-Q8_0.gguf
  --embedding-model models/all-MiniLM-L6-v2
  --port 8000
  --threads 8
  --tmp-dir .tmp
"""

from __future__ import annotations

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

def start_waitress(py: Path, port: int, threads: int, env: dict, detached: bool, log_dir: Path | None) -> None:
    cmd = [str(py), "-m", "waitress", "--listen", f"0.0.0.0:{port}", "--threads", str(threads), "app_rag_chat:app"]
    print(f"[SERVE] Starting waitress on 0.0.0.0:{port} (threads={threads})")

    if detached:
        # background with log redirection
        mkdir(log_dir or (REPO / "logs"))
        log_file = (log_dir or (REPO / "logs")) / "server.out"
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
    else:
        # foreground (blocking)
        run(cmd, cwd=REPO, env=env, check=True)

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
                   help="Server port (default: 8000)")
    ap.add_argument("--threads", type=int, default=8, 
                   help="Waitress threads (default: 8)")
    ap.add_argument("--tmp-dir", type=Path, default=Path(".tmp"), 
                   help="Repo-local temp dir (default: ./.tmp)")
    ap.add_argument("--detached", action="store_true", 
                   help="Run waitress in background")
    ap.add_argument("--skip-etl", action="store_true", 
                   help="Skip ETL build_views_pandas.py")
    ap.add_argument("--skip-index", action="store_true", 
                   help="Skip index build")
    ap.add_argument("--smoke-ask", default='hello', 
                   help="Smoke query question (default: 'hello')")
    ap.add_argument("--smoke-topk", type=int, default=3, 
                   help="Smoke query top-k (default: 3)")
    args = ap.parse_args()

    # force local temp/caches so nothing writes to C:\
    set_repo_local_temp_and_caches(args.tmp_dir)

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

    # runtime env for the app
    app_env = os.environ.copy()
    app_env.setdefault("TRANSFORMERS_OFFLINE", "1")
    app_env.setdefault("HF_HUB_OFFLINE", "1")
    app_env["PORT"] = str(args.port)
    app_env["VIEWS_DIR"] = str(args.views.resolve())
    app_env["LLM_MODEL"] = str(args.model_gguf.resolve())
    app_env["EMBEDDING_MODEL"] = str(args.embedding_model.resolve())

    # serve with waitress (foreground or detached)
    start_waitress(py, args.port, args.threads, app_env, args.detached, log_dir=REPO / "logs")

    print("\n=== READY ===")
    print(f"URL: http://localhost:{args.port}/")
    if args.detached:
        print("Server is running in background. Check logs/server.out for output.")

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

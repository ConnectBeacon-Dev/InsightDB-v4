#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Minimal offline installer with repo-local TEMP/cache.
# Defaults:
#   --requirements  requirements.txt
#   --wheelhouse    wheelhouse
#   --models-dir    models
#   --model-subdir  all-MiniLM-L6-v2
#   --venv          .venv
#   --tmp-dir       .tmp

from __future__ import annotations
import argparse
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

# ---------------- env & fs helpers ----------------

def _mkdir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p

def _set_default_env_paths(tmp_dir: Path | None = None) -> None:
    base_tmp = tmp_dir or (REPO_ROOT / ".tmp")
    _mkdir(base_tmp)
    # Force subprocesses to use repo-local temp
    os.environ["TEMP"] = str(base_tmp)
    os.environ["TMP"] = str(base_tmp)
    os.environ["TMPDIR"] = str(base_tmp)

    os.environ.setdefault("PIP_CACHE_DIR", str(_mkdir(REPO_ROOT / ".pip_cache")))
    os.environ.setdefault("HF_HOME",        str(_mkdir(REPO_ROOT / ".hf_home")))
    os.environ.setdefault("TRANSFORMERS_CACHE", str(_mkdir(REPO_ROOT / ".hf_cache")))
    os.environ.setdefault("TORCH_HOME",     str(_mkdir(REPO_ROOT / ".torch_home")))
    os.environ.setdefault("PIP_DISABLE_PIP_VERSION_CHECK", "1")
    os.environ.setdefault("PIP_NO_INPUT", "1")

# initialize repo-local temp/caches immediately
_set_default_env_paths()

def run(cmd: list[str], cwd: Path | None = None, env: dict | None = None, check: bool = True) -> subprocess.CompletedProcess:
    print(f"\n[RUN] {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env, check=check)

def venv_python_path(venv_dir: Path) -> Path:
    return venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

def venv_pip_path(venv_dir: Path) -> Path:
    return venv_dir / ("Scripts/pip.exe" if os.name == "nt" else "bin/pip")

def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def rmtree_force(path: Path, retries: int = 6, delay: float = 0.5) -> None:
    if not path.exists():
        return
    for _ in range(retries):
        try:
            shutil.rmtree(path, onerror=_on_rm_error)
            if not path.exists():
                return
        except Exception:
            time.sleep(delay)
    if path.exists():
        raise RuntimeError(f"Failed to delete: {path}")

def _on_rm_error(func, path, exc_info):
    try:
        os.chmod(path, stat.S_IWRITE)
    except Exception:
        pass
    try:
        func(path)
    except Exception:
        pass

def canonicalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()

def make_filtered_requirements(orig: Path, exclude: set[str]) -> Path:
    fd, tmp_name = tempfile.mkstemp(prefix="req_filtered_", suffix=".txt")
    os.close(fd)
    tmp = Path(tmp_name)
    with orig.open("r", encoding="utf-8") as fin, tmp.open("w", encoding="utf-8", newline="\n") as fout:
        for raw in fin:
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith("-r "):
                fout.write(raw)
                continue
            m = re.match(r"^\s*([A-Za-z0-9_.\-]+)", line)
            if m and canonicalize_name(m.group(1)) in exclude:
                continue
            fout.write(raw)
    return tmp

def wheel_inventory(wheelhouse: Path) -> set[str]:
    inv: set[str] = set()
    for whl in wheelhouse.glob("*.whl"):
        name = whl.name.split("-")[0]
        inv.add(canonicalize_name(name))
    return inv

def find_wheel(wheelhouse: Path, project_prefix: str) -> Path | None:
    pfx = canonicalize_name(project_prefix).replace("-", "_")
    cands = sorted([w for w in wheelhouse.glob("*.whl") if w.name.lower().startswith(pfx)])
    return cands[-1] if cands else None

def _offline_env() -> dict:
    env = os.environ.copy()
    env["PIP_NO_INDEX"] = "1"
    env["TRANSFORMERS_OFFLINE"] = "1"
    env["HF_HUB_OFFLINE"] = "1"
    return env

def try_import(python_exe: Path, module: str) -> tuple[bool, str]:
    code = f"import importlib,sys; print('OK' if importlib.util.find_spec('{module}') else 'MISSING')"
    cp = subprocess.run([str(python_exe), "-c", code], capture_output=True, text=True, env=_offline_env(), check=False)
    out = (cp.stdout or "").strip()
    return (out == "OK", out)

# ---------------- core workflow ----------------

def create_or_recreate_venv(venv_dir: Path, recreate: bool) -> None:
    if recreate and venv_dir.exists():
        print(f"[VENV] Recreating venv at {venv_dir}")
        rmtree_force(venv_dir)
    if not venv_dir.exists():
        print(f"[VENV] Creating venv at {venv_dir}")
        run([sys.executable, "-m", "venv", str(venv_dir)])
    else:
        print(f"[VENV] Using existing venv at {venv_dir}")

def offline_upgrade_tooling(pip_exe: Path, wheelhouse: Path) -> None:
    present = []
    for w in wheelhouse.glob("*.whl"):
        n = canonicalize_name(w.name.split("-")[0])
        if n in {"pip", "setuptools", "wheel"}:
            present.append(n)
    if present:
        print(f"[VENV] Offline-upgrading tooling available: {sorted(set(present))}")
        try:
            run([str(pip_exe), "install", "--no-index", f"--find-links={wheelhouse}", "-U", *sorted(set(present))], env=_offline_env())
        except subprocess.CalledProcessError:
            print("[WARN] Tooling upgrade failed (continuing).")

def ensure_diskcache(pip_exe: Path, wheelhouse: Path) -> None:
    """
    Always try to install diskcache offline. If the versioned spec fails,
    fall back to the explicit wheel file if present.
    """
    print("[PRE] Ensuring diskcache (>=5.6.1) from wheelhouse…")
    try:
        run([str(pip_exe), "install", "--no-index", f"--find-links={wheelhouse}", "--only-binary=:all:", "diskcache>=5.6.1"], env=_offline_env(), check=True)
        print("[PRE] diskcache installed/verified.")
        return
    except subprocess.CalledProcessError as e:
        print(f"[WARN] Spec install failed (exit {e.returncode}); trying explicit wheel…")
        wh = find_wheel(wheelhouse, "diskcache")
        if wh:
            try:
                run([str(pip_exe), "install", "--no-index", str(wh)], env=_offline_env(), check=True)
                print("[PRE] diskcache installed from explicit wheel.")
                return
            except subprocess.CalledProcessError as e2:
                print(f"[WARN] Explicit wheel install failed (exit {e2.returncode}).")
        else:
            print("[WARN] No diskcache wheel found in wheelhouse.")

def install_local_llama_wheel_no_deps(pip_exe: Path, wheelhouse: Path) -> None:
    wh = find_wheel(wheelhouse, "llama_cpp_python") or find_wheel(wheelhouse, "llama-cpp-python")
    if not wh:
        raise SystemExit("[ERROR] No llama-cpp-python wheel found in wheelhouse (expected after make_wheelhouse.py).")
    print(f"[PRE] Installing local llama-cpp-python (no deps) → {wh.name}")
    run([str(pip_exe), "install", "--no-index", str(wh), "--no-deps"], env=_offline_env())

def install_offline_requirements_excluding_llama(pip_exe: Path, wheelhouse: Path, requirements: Path) -> None:
    filtered = make_filtered_requirements(requirements, exclude={"llama-cpp-python"})
    try:
        print("\n[INSTALL] Requirements (llama-cpp-python excluded) from wheelhouse…")
        run([str(pip_exe), "install", "--no-index", f"--find-links={wheelhouse}", "-r", str(filtered)], env=_offline_env())
    finally:
        try:
            filtered.unlink(missing_ok=True)  # type: ignore[arg-type]
        except Exception:
            pass

def test_imports(python_exe: Path) -> dict:
    code = r"""
import importlib, json
mods = ["pandas","numpy","torch","transformers","sentence_transformers","flask","llama_cpp"]
res = {}
for m in mods:
    try:
        mod = importlib.import_module(m)
        ver = getattr(mod, "__version__", "OK")
        res[m] = f"OK ({ver})"
    except Exception as e:
        res[m] = f"ERROR: {e.__class__.__name__}: {e}"
print(json.dumps(res, ensure_ascii=False))
"""
    cp = subprocess.run([str(python_exe), "-c", code], capture_output=True, text=True, env=_offline_env(), check=False)
    try:
        return json.loads(cp.stdout.strip() or "{}")
    except Exception:
        return {}

def test_local_model(python_exe: Path, model_dir: Path) -> dict:
    code = rf"""
import json, os
os.environ.setdefault("TRANSFORMERS_OFFLINE","1")
os.environ.setdefault("HF_HUB_OFFLINE","1")
try:
    from sentence_transformers import SentenceTransformer
    mdl = SentenceTransformer(r"{model_dir}")
    vec = mdl.encode(["hello world"], batch_size=1, show_progress_bar=False)
    print(json.dumps({{"ok": True, "dim": int(len(vec[0]))}}))
except Exception as e:
    print(json.dumps({{"ok": False, "error": str(e)}}))
"""
    cp = subprocess.run([str(python_exe), "-c", code], capture_output=True, text=True, env=_offline_env(), check=False)
    try:
        return json.loads(cp.stdout.strip() or "{}")
    except Exception:
        return {"ok": False, "error": "could not parse test output"}

def guess_model_ok(model_dir: Path) -> tuple[bool, str]:
    if not model_dir.exists():
        return False, f"missing: {model_dir}"
    expected_any = [
        model_dir / "config.json",
        model_dir / "tokenizer.json",
        model_dir / "tokenizer.model",
        model_dir / "pytorch_model.bin",
        model_dir / "model.safetensors",
        model_dir / "sentence_bert_config.json",
    ]
    if any(p.exists() for p in expected_any):
        return True, "found core model files"
    return False, "no expected model files found (config/tokenizer/weights)"

# ---------------- CLI ----------------

def main():
    p = argparse.ArgumentParser(description="Offline venv installer + verifier (repo-local temp/caches).")
    p.add_argument("--requirements", "-r", type=Path, default=Path("requirements.txt"))
    p.add_argument("--wheelhouse", "-w", type=Path, default=Path("wheelhouse"))
    p.add_argument("--models-dir", "-m", type=Path, default=Path("models"))
    p.add_argument("--venv", type=Path, default=Path(".venv"))
    p.add_argument("--model-subdir", default="all-MiniLM-L6-v2")
    p.add_argument("--recreate", action="store_true")
    p.add_argument("--tmp-dir", type=Path, default=None)
    args = p.parse_args()

    _set_default_env_paths(args.tmp_dir)

    print(f"[TEMP] tempfile.gettempdir() = {tempfile.gettempdir()}")
    print(f"[TEMP] ENV TEMP={os.getenv('TEMP')} | TMP={os.getenv('TMP')} | TMPDIR={os.getenv('TMPDIR')}")
    print(f"[CACHE] PIP_CACHE_DIR={os.getenv('PIP_CACHE_DIR')}")
    print(f"[CACHE] HF_HOME={os.getenv('HF_HOME')} | TRANSFORMERS_CACHE={os.getenv('TRANSFORMERS_CACHE')} | TORCH_HOME={os.getenv('TORCH_HOME')}")

    req = args.requirements.resolve()
    wheelhouse = args.wheelhouse.resolve()
    models_root = args.models_dir.resolve()
    model_dir = (models_root / args.model_subdir).resolve()
    venv_dir = args.venv.resolve()

    if not req.exists():
        raise SystemExit(f"[ERROR] requirements file not found: {req}")
    if not wheelhouse.exists():
        raise SystemExit(f"[ERROR] wheelhouse not found: {wheelhouse}")
    ensure_dir(models_root)

    create_or_recreate_venv(venv_dir, args.recreate)
    py = venv_python_path(venv_dir)
    pip = venv_pip_path(venv_dir)
    if not py.exists():
        raise SystemExit(f"[ERROR] venv python not found at {py}")
    if not pip.exists():
        raise SystemExit(f"[ERROR] venv pip not found at {pip}")

    offline_upgrade_tooling(pip, wheelhouse)

    inv = wheel_inventory(wheelhouse)
    shown = ", ".join(sorted(list(inv))[:12]) + ("…" if len(inv) > 12 else "")
    print(f"\n[VERIFY] Wheelhouse projects detected ({len(inv)}): {shown}")

    ok_m, msg = guess_model_ok(model_dir)
    print(f"[MODEL] {model_dir} → {msg}")

    # Install sequence
    ensure_diskcache(pip, wheelhouse)                  # <-- now unconditional
    install_local_llama_wheel_no_deps(pip, wheelhouse)
    install_offline_requirements_excluding_llama(pip, wheelhouse, req)

    print("\n[TEST] Importing key packages inside the venv…")
    res = test_imports(py)
    for k in ["pandas","numpy","torch","transformers","sentence_transformers","flask","llama_cpp"]:
        print(f"  {k:24s} {res.get(k,'N/A')}")

    # Retry llama_cpp import after forcing diskcache, if it still complains
    if "diskcache" in (res.get("llama_cpp","").lower()):
        print("\n[FIXUP] llama_cpp complained about diskcache. Retesting after forced install…")
        ok, _ = try_import(py, "llama_cpp")
        print(f"[RETEST] llama_cpp import after fix: {'OK' if ok else 'FAILED'}")

    print("\n[TEST] Loading local Sentence-Transformers model and encoding a sample…")
    mres = test_local_model(py, model_dir)
    if mres.get("ok"):
        print(f"  Model OK. Embedding dim = {mres.get('dim')}")
    else:
        print(f"  Model load FAILED: {mres.get('error')}")

    print("\n=== OFFLINE INSTALL COMPLETE ===")
    if os.name == "nt":
        print(f"Activate: {venv_dir}\\Scripts\\activate")
        print(f"Or run without activating:\n  {venv_dir}\\Scripts\\python.exe -c \"import torch; print(torch.__version__)\"")
    else:
        print(f"source {venv_dir}/bin/activate")

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

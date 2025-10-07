#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
make_wheelhouse.py (minimal, zero-arg)

Usage:
  python make_wheelhouse.py

Assumes (fixed paths):
  - requirements.txt          (root)
  - wheelhouse/               (output, will be DELETED)
  - models/                   (model root; ONLY 'all-MiniLM-L6-v2' subfolder will be DELETED)

What it does:
  1) Clean wheelhouse + models/all-MiniLM-L6-v2
  2) Download wheels for requirements (excluding torch/llama-cpp-python initially)
  3) Ensure torch (CPU) wheels (2.8.0)
  4) Ensure waitress wheel (==2.1.2)
  5) Ensure diskcache wheel (version read from requirements)
  6) Ensure Flask-CORS wheel (version read from requirements — e.g., 6.0.1)
  7) Ensure llama-cpp-python wheel (prebuilt → install-and-capture → robust local build if needed)
  8) Download model: sentence-transformers/all-MiniLM-L6-v2
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path
from shutil import which

# ---------- Fixed paths / defaults ----------
REPO           = Path(__file__).resolve().parent
REQUIREMENTS   = REPO / "requirements.txt"
WHEELHOUSE     = REPO / "wheelhouse"
MODELS_DIR     = REPO / "models"
MODEL_REPO_ID  = "sentence-transformers/all-MiniLM-L6-v2"
WAITRESS_VER   = "2.1.2"
TMP_DIR        = REPO / ".tmp"

# Torch channel (CPU)
CHANNEL_INDEX = {
    "cpu": "https://download.pytorch.org/whl/cpu",
}

# ---------- Small helpers ----------
def set_repo_local_temp_and_caches():
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("TEMP", str(TMP_DIR))
    os.environ.setdefault("TMP", str(TMP_DIR))
    os.environ.setdefault("TMPDIR", str(TMP_DIR))
    os.environ.setdefault("PIP_CACHE_DIR", str(REPO / ".pip_cache"))
    os.environ.setdefault("HF_HOME", str(REPO / ".hf_home"))
    os.environ.setdefault("TRANSFORMERS_CACHE", str(REPO / ".hf_cache"))
    os.environ.setdefault("TORCH_HOME", str(REPO / ".torch_home"))
    os.environ.setdefault("PIP_DISABLE_PIP_VERSION_CHECK", "1")

def run(cmd: list[str], cwd: Path | None = None, env: dict | None = None, check: bool = True):
    print(f"\n[RUN] {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env, check=check)

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def _on_rm_error(func, path, exc_info):
    try:
        os.chmod(path, stat.S_IWRITE)
    except Exception:
        pass
    try:
        func(path)
    except Exception:
        pass

def rmtree_force(path: Path, retries: int = 6, delay: float = 0.5):
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

def has_wheel(out: Path, name_prefix: str) -> bool:
    pfx = name_prefix.lower().replace("-", "_")
    return any(whl.name.lower().startswith(pfx) for whl in out.glob("*.whl"))

def find_wheel(out: Path, name_prefix: str) -> Path | None:
    pfx = name_prefix.lower().replace("-", "_")
    cands = sorted([w for w in out.glob("*.whl") if w.name.lower().startswith(pfx)])
    return cands[-1] if cands else None

def pip(*args: str) -> list[str]:
    return [sys.executable, "-m", "pip", *args]

def is_windows() -> bool:
    return platform.system().lower().startswith("win")

def normalize_repo_id(repo_id: str) -> str:
    return repo_id.rstrip("/").split("/")[-1]

# ---------- Parse pinned versions from requirements ----------
_name_re = re.compile(r"^\s*([A-Za-z0-9_.\-]+)")

def _canon(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()

def parse_pins_from_requirements(req: Path) -> dict[str, str]:
    """
    Returns a mapping of canonicalized package name -> exact '==x.y.z' or spec string.
    """
    pins: dict[str, str] = {}
    if not req.exists():
        return pins
    for raw in req.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("-r "):
            continue
        m = _name_re.match(line)
        if not m:
            continue
        name = _canon(m.group(1))
        # keep full spec after the name (e.g., ==1.2.3, >=, etc.)
        spec = line[len(m.group(1)) :].strip()
        if spec:
            pins[name] = spec
        else:
            pins[name] = ""
    return pins

# ---------- Requirements filtering ----------
# we exclude torch and llama-cpp-python from the initial download (handled explicitly)
EXCLUDE_PKGS = {"llama-cpp-python", "torch", "torchvision", "torchaudio"}

def make_filtered_requirements(orig: Path) -> Path:
    fd, tmp_name = tempfile.mkstemp(prefix="req_filtered_", suffix=".txt", dir=str(TMP_DIR))
    os.close(fd)
    tmp = Path(tmp_name)
    skipped = []
    with orig.open("r", encoding="utf-8") as fin, tmp.open("w", encoding="utf-8", newline="\n") as fout:
        for raw in fin:
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith("-r "):
                fout.write(raw + ("\n" if not raw.endswith("\n") else ""))
                continue
            m = _name_re.match(line)
            if m:
                name = _canon(m.group(1))
                if name in EXCLUDE_PKGS:
                    skipped.append(name)
                    continue
            fout.write(raw + ("\n" if not raw.endswith("\n") else ""))
    print(f"[FILTER] Excluded: {sorted(set(skipped)) or 'none'}")
    return tmp

# ---------- Torch wheels ----------
def ensure_torch_wheels(out: Path, channel: str = "cpu"):
    if has_wheel(out, "torch"):
        print("[TORCH] wheel already present.")
        return
    index_url = CHANNEL_INDEX[channel]
    print(f"[TORCH] Downloading torch from {index_url}")
    run(pip("download", "-d", str(out), "--only-binary=:all:", "--prefer-binary",
            "--index-url", index_url, "torch==2.8.0"))

# ---------- Waitress wheel ----------
def ensure_waitress_wheel(out: Path, version: str = WAITRESS_VER):
    if has_wheel(out, "waitress"):
        print("[SERVE] waitress wheel already present.")
        return
    print(f"[SERVE] Downloading waitress=={version}")
    run(pip("download", f"waitress=={version}", "-d", str(out), "--only-binary=:all:", "--prefer-binary"))

# ---------- Diskcache wheel (sync with requirements) ----------
def ensure_diskcache_wheel(out: Path, req_pins: dict[str, str]):
    if has_wheel(out, "diskcache"):
        print("[DISKCACHE] wheel already present.")
        return
    spec = req_pins.get("diskcache", ">=5.6.1")
    want = f"diskcache{spec}" if spec else "diskcache"
    print(f"[DISKCACHE] Downloading {want}")
    run(pip("download", want, "-d", str(out), "--only-binary=:all:", "--prefer-binary"))

# ---------- Flask-CORS wheel (sync with requirements) ----------
def ensure_flask_cors_wheel(out: Path, req_pins: dict[str, str]):
    # On PyPI it's project 'Flask-Cors' (case-insensitive). Wheel filename prefix is 'Flask_Cors-...'
    if has_wheel(out, "flask_cors"):
        print("[CORS] Flask-CORS wheel already present.")
        return
    spec = req_pins.get("flask-cors", "") or req_pins.get("flask_cors", "")
    want = f"Flask-Cors{spec}" if spec else "Flask-Cors"
    print(f"[CORS] Downloading {want}")
    run(pip("download", want, "-d", str(out), "--only-binary=:all:", "--prefer-binary"))

# ---------- llama-cpp-python helpers ----------
def try_download_llama(out: Path, version: str | None) -> bool:
    pkg = "llama-cpp-python" + (f"=={version}" if version else "")
    try:
        run(pip("download", pkg, "-d", str(out), "--only-binary=:all:", "--prefer-binary"))
    except subprocess.CalledProcessError:
        return False
    return has_wheel(out, "llama_cpp_python")

def _windows_msvc_or_clangcl_env() -> dict | None:
    env_add = {}
    if which("cl"):
        print("[LLAMA][WIN] Found MSVC cl.exe (Ninja).")
        env_add["CMAKE_C_COMPILER"] = "cl"
        env_add["CMAKE_CXX_COMPILER"] = "cl"
        env_add["CMAKE_GENERATOR"] = "Ninja"
        return env_add
    if which("clang-cl"):
        print("[LLAMA][WIN] Found clang-cl (Ninja).")
        env_add["CMAKE_C_COMPILER"] = "clang-cl"
        env_add["CMAKE_CXX_COMPILER"] = "clang-cl"
        env_add["CMAKE_GENERATOR"] = "Ninja"
        return env_add
    return None

TOOLS_DIR = REPO / "tools"
W64_DIR   = TOOLS_DIR / "w64devkit"
W64_SFX   = TOOLS_DIR / "w64devkit-x64-2.3.0.7z.exe"
W64_URL   = "https://github.com/skeeto/w64devkit/releases/download/v2.3.0/w64devkit-x64-2.3.0.7z.exe"

def _download_w64devkit() -> Path:
    ensure_dir(TOOLS_DIR)
    if not W64_SFX.exists():
        print(f"[W64] Downloading → {W64_SFX}")
        urllib.request.urlretrieve(W64_URL, str(W64_SFX))
    else:
        print(f"[W64] Archive present → {W64_SFX}")
    return W64_SFX

def _extract_w64devkit() -> Path:
    sfx = _download_w64devkit()
    out_dir = str((W64_DIR.parent).resolve())
    if not out_dir.endswith(os.sep):
        out_dir += os.sep
    print(f"[W64] Extracting into {out_dir}")
    subprocess.run([str(sfx), "-y", f"-o{out_dir}"], check=True)
    bin_dir = (W64_DIR / "bin").resolve()
    if not bin_dir.exists():
        raise RuntimeError(f"[W64] Extraction failed; missing {bin_dir}")
    return bin_dir

def _cpu_flags_merge(env: dict) -> dict:
    """
    Universal Windows/Intel build profile for llama-cpp-python:
    - CPU-only
    - SSE3 baseline (AVX/AVX2/FMA/F16C/AVX-512 OFF) to avoid 0xC000001D on old/VM hosts
    - OpenMP ON for better multi-thread CPU throughput
    """
    need_cmake = [
        "-DLLAMA_NATIVE=OFF",
        "-DLLAMA_BLAS=OFF",
        "-DLLAMA_CUBLAS=OFF",
        "-DGGML_BLAS=OFF",
        "-DGGML_OPENMP=ON",
        "-DGGML_CUDA=OFF",
        "-DGGML_AVX=OFF",
        "-DGGML_AVX2=OFF",
        "-DGGML_FMA=OFF",
        "-DGGML_F16C=OFF",
        "-DGGML_SSE3=ON",
        "-DGGML_AVX512=OFF",
        "-DLLAMA_BUILD_TESTS=OFF",
        "-DLLAMA_BUILD_EXAMPLES=OFF",
        "-DCMAKE_CXX_STANDARD=17",
    ]
    cm = env.get("CMAKE_ARGS", "")
    for flag in need_cmake:
        if flag not in cm:
            cm += (" " if cm else "") + flag
    env["CMAKE_ARGS"] = cm.strip()
    # Remove any aggressive arch flags that could sneak in from environment
    env.pop("CFLAGS", None)
    env.pop("CXXFLAGS", None)
    return env

def _windows_mingw_env() -> dict:
    bin_dir = _extract_w64devkit()
    gcc  = (bin_dir / "gcc.exe").resolve()
    gxx  = (bin_dir / "g++.exe").resolve()
    make = (bin_dir / "make.exe").resolve()
    for exe in (gcc, gxx, make):
        if not exe.exists():
            raise RuntimeError(f"[W64] Missing tool: {exe}")
    gcc_p, gxx_p, make_p = gcc.as_posix(), gxx.as_posix(), make.as_posix()
    env = os.environ.copy()
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    env["CC"] = gcc_p
    env["CXX"] = gxx_p
    env["CMAKE_GENERATOR"] = "MinGW Makefiles"
    env["CMAKE_MAKE_PROGRAM"] = make_p
    env["CMAKE_SH"] = "CMAKE_SH-NOTFOUND"
    injected = [
        f"-DCMAKE_C_COMPILER={gcc_p}",
        f"-DCMAKE_CXX_COMPILER={gxx_p}",
        f"-DCMAKE_MAKE_PROGRAM={make_p}",
    ]
    env["CMAKE_ARGS"] = (env.get("CMAKE_ARGS", "") + " " + " ".join(injected)).strip()
    env["LLAMA_CUBLAS"] = "0"
    env["FORCE_CMAKE"] = "1"
    print("[W64] Using MinGW toolchain")
    return env

def _pip_download_sdist_llama(version: str | None, dest: Path) -> Path:
    pkg = "llama-cpp-python" + (f"=={version}" if version else "")
    dl_env = os.environ.copy()
    dl_env.setdefault("PIP_NO_BUILD_ISOLATION", "1")
    dl_env.setdefault("PIP_DISABLE_PIP_VERSION_CHECK", "1")
    run([sys.executable, "-m", "pip", "download", "--no-binary=:all:", "--no-deps", pkg, "-d", str(dest)], env=dl_env)
    tars = list(dest.glob("llama-cpp-python-*.tar.gz")) + list(dest.glob("llama-cpp-python-*.zip"))
    if not tars:
        raise RuntimeError("Could not download llama-cpp-python sdist.")
    return sorted(tars)[-1]

def _extract_sdist(archive: Path, into: Path) -> Path:
    ensure_dir(into)
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive, "r") as zf:
            zf.extractall(into)
    else:
        with tarfile.open(archive, "r:gz") as tf:
            tf.extractall(into)
    roots = [p for p in into.iterdir() if p.is_dir() and (p / "pyproject.toml").exists()]
    if not roots:
        roots = [p for p in into.iterdir() if p.is_dir()]
    if not roots:
        raise RuntimeError("Failed to locate sdist root.")
    return sorted(roots)[-1]

def _patch_llama_mmap_add_cstdint(src_root: Path) -> bool:
    header = src_root / "vendor" / "llama.cpp" / "src" / "llama-mmap.h"
    if not header.exists():
        return False
    txt = header.read_text(encoding="utf-8", errors="ignore")
    if "cstdint" in txt:
        return False
    lines = txt.splitlines()
    insert_idx = 0
    for i, line in enumerate(lines[:50]):
        if line.strip().startswith("#include"):
            insert_idx = i + 1
        elif line.strip() and not line.strip().startswith("#"):
            break
    lines.insert(insert_idx, "#include <cstdint>")
    header.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("[PATCH] Added <cstdint> to llama-mmap.h")
    return True

def _build_llama_wheel_from_src(out: Path, src_root: Path, base_env: dict):
    env = _cpu_flags_merge(base_env.copy())
    run(pip("wheel", str(src_root), "-w", str(out.resolve())), env=env)
    wh = find_wheel(out, "llama_cpp_python")
    if not wh:
        raise RuntimeError("Build-from-source produced no wheel.")

def _build_llama_wheel(out: Path, version: str | None):
    print("[LLAMA] Building wheel from source (CPU)…")
    run(pip("install", "--upgrade", "pip", "wheel", "build", "cmake", "ninja", "scikit-build-core"))
    base_env = os.environ.copy()
    if is_windows():
        msvc = _windows_msvc_or_clangcl_env()
        if msvc:
            base_env.update(msvc)
        else:
            base_env = _windows_mingw_env()
    base_env = _cpu_flags_merge(base_env)
    pkg = "llama-cpp-python" + (f"=={version}" if version else "")
    try:
        run(pip("wheel", pkg, "-w", str(out.resolve())), env=base_env)
        if not find_wheel(out, "llama_cpp_python"):
            raise RuntimeError("Wheel build finished but wheel missing.")
        return
    except Exception:
        print("[LLAMA] Direct wheel build failed; trying sdist patch path…")
    with tempfile.TemporaryDirectory(dir=str(TMP_DIR)) as td:
        tmpdir = Path(td)
        sdist = _pip_download_sdist_llama(version, tmpdir)
        src_root = _extract_sdist(sdist, tmpdir / "src")
        _patch_llama_mmap_add_cstdint(src_root)
        _build_llama_wheel_from_src(out, src_root, base_env)

def _try_install_then_capture(out: Path, version: str | None) -> bool:
    pkg = "llama-cpp-python" + (f"=={version}" if version else "")
    base_env = os.environ.copy()
    if is_windows():
        msvc = _windows_msvc_or_clangcl_env()
        if msvc:
            base_env.update(msvc)
        else:
            base_env = _windows_mingw_env()
    base_env = _cpu_flags_merge(base_env)
    try:
        print("[LLAMA] Trying quick: pip install --no-deps", pkg)
        run(pip("install", "--no-deps", pkg), env=base_env)
        print("[LLAMA] Capturing wheel into wheelhouse…")
        run(pip("wheel", "--no-deps", pkg, "-w", str(out.resolve())), env=base_env)
        if find_wheel(out, "llama_cpp_python"):
            try:
                run(pip("uninstall", "-y", "llama-cpp-python"))
            except Exception:
                pass
            return True
    except Exception:
        try:
            run(pip("uninstall", "-y", "llama-cpp-python"))
        except Exception:
            pass
    return False

def ensure_llama_wheel(out: Path) -> Path:
    wh = find_wheel(out, "llama_cpp_python")
    if wh:
        print(f"[LLAMA] Wheel present: {wh.name}")
        return wh
    print("[LLAMA] Searching for prebuilt wheel…")
    if try_download_llama(out, None):
        return find_wheel(out, "llama_cpp_python")
    for ver in ["0.3.16", "0.3.6", "0.3.5", "0.2.79"]:
        if try_download_llama(out, ver):
            return find_wheel(out, "llama_cpp_python")
    print("[LLAMA] Prebuilt not found. Trying install-and-capture…")
    for ver in ["0.3.16", "0.3.6", None]:
        if _try_install_then_capture(out, ver):
            return find_wheel(out, "llama_cpp_python")
    print("[LLAMA] Falling back to robust local build…")
    _build_llama_wheel(out, "0.3.16")
    wh = find_wheel(out, "llama_cpp_python")
    if not wh:
        raise SystemExit("[LLAMA] Build completed but no wheel produced.")
    return wh

# ---------- Model download ----------
def ensure_package_installed(pkg: str):
    try:
        __import__(pkg)
    except ImportError:
        run(pip("install", "--upgrade", pkg))

def download_model(repo_id: str, dest_dir: Path):
    ensure_package_installed("huggingface_hub")
    from huggingface_hub import snapshot_download
    friendly = normalize_repo_id(repo_id)
    final_dir = dest_dir / friendly
    ensure_dir(final_dir)
    print(f"\n[MODEL] Downloading '{repo_id}' → {final_dir} (fresh)")
    snapshot_download(
        repo_id=repo_id,
        local_dir=str(final_dir),
        local_dir_use_symlinks=False,
        resume_download=False,
        allow_patterns=None,
    )
    print("[MODEL] Done.")

# ---------- Main ----------
def main():
    if not REQUIREMENTS.exists():
        raise SystemExit(f"[ERROR] Missing {REQUIREMENTS}")
    set_repo_local_temp_and_caches()

    # Read pins (to sync diskcache / flask-cors steps with requirements)
    pins = parse_pins_from_requirements(REQUIREMENTS)

    model_subdir = MODELS_DIR / normalize_repo_id(MODEL_REPO_ID)

    # Clean
    if WHEELHOUSE.exists():
        print(f"\n[CLEAN] Removing wheelhouse: {WHEELHOUSE}")
        rmtree_force(WHEELHOUSE)
    if model_subdir.exists():
        print(f"\n[CLEAN] Removing model dir: {model_subdir}")
        rmtree_force(model_subdir)
    ensure_dir(WHEELHOUSE)
    ensure_dir(MODELS_DIR)

    # Filter reqs
    filtered = make_filtered_requirements(REQUIREMENTS)

    try:
        # Step 1: download filtered reqs (pure wheels)
        print("\n=== STEP 1: Downloading filtered requirements ===")
        run(pip("download", "-r", str(filtered), "-d", str(WHEELHOUSE),
                "--only-binary=:all:", "--prefer-binary"))

        # Step 2: torch (cpu) pinned 2.8.0
        print("\n=== STEP 2: Ensuring torch (CPU) ===")
        ensure_torch_wheels(WHEELHOUSE, channel="cpu")

        # Step 2.5: waitress (explicit pin)
        print("\n=== STEP 2.5: Ensuring waitress ===")
        ensure_waitress_wheel(WHEELHOUSE, version=WAITRESS_VER)

        # Step 2.6: diskcache (sync with requirements)
        print("\n=== STEP 2.6: Ensuring diskcache ===")
        ensure_diskcache_wheel(WHEELHOUSE, pins)

        # Step 2.7: Flask-CORS (sync with requirements, e.g., 6.0.1)
        print("\n=== STEP 2.7: Ensuring Flask-CORS ===")
        ensure_flask_cors_wheel(WHEELHOUSE, pins)

        # Step 3: llama-cpp-python
        print("\n=== STEP 3: Ensuring llama-cpp-python ===")
        _ = ensure_llama_wheel(WHEELHOUSE)
        print(f"[LLAMA] Ready: {find_wheel(WHEELHOUSE, 'llama_cpp_python').name}")

        # Step 4: model
        print("\n=== STEP 4: Downloading model ===")
        download_model(MODEL_REPO_ID, MODELS_DIR)

        # Summary
        print("\n=== DONE (fresh wheelhouse + model) ===")
        print(f"Wheelhouse: {WHEELHOUSE}")
        print(f"Model dir:  {model_subdir}")
        print("\nOffline install example:")
        print(f"  pip install --no-index --find-links={WHEELHOUSE} -r {REQUIREMENTS}")

    finally:
        try:
            filtered.unlink(missing_ok=True)  # type: ignore[arg-type]
        except Exception:
            pass

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

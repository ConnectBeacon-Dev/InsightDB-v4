#!/usr/bin/env python3
"""
make_wheelhouse.py

Build an offline wheelhouse for a requirements.txt and download a SentenceTransformers model.

Examples (CPU-only Torch, download MiniLM to ./models):
    python make_wheelhouse.py --requirements requirements.txt --out wheelhouse --models-dir models

Include torchvision/torchaudio wheels as well:
    python make_wheelhouse.py --requirements requirements.txt --out wheelhouse --models-dir models --torch-extras

Use CUDA 12.1 torch channel instead of CPU:
    python make_wheelhouse.py --requirements requirements.txt --out wheelhouse --models-dir models --torch-channel cu121

Try to build llama-cpp-python wheel locally if a prebuilt wheel isn't found:
    python make_wheelhouse.py --requirements requirements.txt --out wheelhouse --models-dir models --build-llama

Afterwards (offline install):
    python -m venv .venv && ./.venv/Scripts/activate  (Windows)
    source .venv/bin/activate                        (Linux/macOS)
    pip install --no-index --find-links=wheelhouse -r requirements.txt

Your code should load the model from the local path:
    SentenceTransformer("models/all-MiniLM-L6-v2")
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

# --------------------------
# Helpers
# --------------------------
def run(cmd:list[str], cwd:Path|None=None, env:dict|None=None) -> None:
    """Run a subprocess with pretty printing."""
    print(f"\n[RUN] {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env, check=True)

def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def has_wheel(out: Path, name_prefix: str) -> bool:
    for whl in out.glob("*.whl"):
        if whl.name.lower().startswith(name_prefix.lower().replace("-", "_")):
            return True
    return False

def pip(*args: str) -> list[str]:
    return [sys.executable, "-m", "pip", *args]

def normalize_repo_id(repo_id: str) -> str:
    # maps "sentence-transformers/all-MiniLM-L6-v2" -> "all-MiniLM-L6-v2"
    return repo_id.rstrip("/").split("/")[-1]

# --------------------------
# Torch channels
# --------------------------
CHANNEL_INDEX = {
    "cpu":    "https://download.pytorch.org/whl/cpu",
    "cu118":  "https://download.pytorch.org/whl/cu118",
    "cu121":  "https://download.pytorch.org/whl/cu121",
    "cu124":  "https://download.pytorch.org/whl/cu124",
    "rocm6.0":"https://download.pytorch.org/whl/rocm6.0",
    "rocm6.1":"https://download.pytorch.org/whl/rocm6.1",
}

# --------------------------
# Hugging Face model download
# --------------------------
def ensure_package_installed(pkg: str) -> None:
    try:
        __import__(pkg)
    except ImportError:
        run(pip("install", "--upgrade", pkg))

def download_model(repo_id: str, dest_dir: Path) -> None:
    """
    Use huggingface_hub to download a full snapshot (no symlinks).
    """
    ensure_package_installed("huggingface_hub")
    from huggingface_hub import snapshot_download
    friendly = normalize_repo_id(repo_id)
    final_dir = dest_dir / friendly
    ensure_dir(final_dir)

    print(f"\n[MODEL] Downloading '{repo_id}' → {final_dir}")
    snapshot_download(
        repo_id=repo_id,
        local_dir=str(final_dir),
        local_dir_use_symlinks=False,
        resume_download=True,
        allow_patterns=None,  # all files
    )
    print("[MODEL] Done.")

# --------------------------
# Llama-cpp handle
# --------------------------
def ensure_llama_cpp_wheel(out: Path, build_if_missing: bool) -> None:
    if has_wheel(out, "llama_cpp_python"):
        print("[LLAMA] Found llama-cpp-python wheel in wheelhouse.")
        return

    # Try to download a prebuilt wheel first
    try:
        run(pip("download", "llama-cpp-python", "-d", str(out), "--only-binary=:all:", "--prefer-binary"))
        if has_wheel(out, "llama_cpp_python"):
            print("[LLAMA] Downloaded prebuilt llama-cpp-python wheel.")
            return
    except subprocess.CalledProcessError:
        pass

    if not build_if_missing:
        print("[LLAMA] No prebuilt wheel found. Use --build-llama to attempt a local CPU build.")
        return

    # Build a wheel locally (CPU). Requires build toolchain (CMake/Ninja/MSVC or gcc/clang).
    print("[LLAMA] Building llama-cpp-python wheel locally (CPU)…")
    try:
        run(pip("install", "--upgrade", "build", "cmake", "ninja", "scikit-build-core"))
        run(pip("wheel", "llama-cpp-python", "-w", str(out)))
        if has_wheel(out, "llama_cpp_python"):
            print("[LLAMA] Built llama-cpp-python wheel successfully.")
        else:
            print("[LLAMA] Build finished but did not find wheel. Please check build logs.")
    except subprocess.CalledProcessError as e:
        print("[LLAMA] Building llama-cpp-python failed. Install C/C++ toolchain, CMake, and Ninja, then retry.")
        raise e

# --------------------------
# Torch wheel capture
# --------------------------
def ensure_torch_wheels(out: Path, channel: str, include_extras: bool) -> None:
    needed = ["torch"]
    if include_extras:
        needed += ["torchvision", "torchaudio"]

    missing = [pkg for pkg in needed if not has_wheel(out, pkg)]
    if not missing:
        print("[TORCH] Torch (and extras if requested) already present.")
        return

    if channel not in CHANNEL_INDEX:
        raise SystemExit(f"[TORCH] Unknown --torch-channel '{channel}'. Choose one of: {', '.join(CHANNEL_INDEX)}")

    index_url = CHANNEL_INDEX[channel]
    print(f"[TORCH] Fetching {', '.join(missing)} from {index_url}")
    run(pip("download", "-d", str(out), "--only-binary=:all:", "--prefer-binary", "--index-url", index_url, *missing))
    print("[TORCH] Done.")

# --------------------------
# Main flow
# --------------------------
def main():
    ap = argparse.ArgumentParser(description="Create a wheelhouse and download a SentenceTransformers model.")
    ap.add_argument("--requirements", "-r", type=Path, required=True, help="Path to requirements.txt")
    ap.add_argument("--out", "-o", type=Path, default=Path("wheelhouse"), help="Output folder for wheels")
    ap.add_argument("--models-dir", type=Path, default=Path("models"), help="Folder to store downloaded models")
    ap.add_argument("--model-repo", default="sentence-transformers/all-MiniLM-L6-v2",
                    help="HF repo id to download (default: sentence-transformers/all-MiniLM-L6-v2)")
    ap.add_argument("--torch-channel", default="cpu", choices=list(CHANNEL_INDEX.keys()),
                    help="PyTorch wheel channel (default: cpu)")
    ap.add_argument("--torch-extras", action="store_true", help="Also capture torchvision and torchaudio wheels")
    ap.add_argument("--build-llama", action="store_true", help="Build llama-cpp-python wheel if prebuilt not found")
    ap.add_argument("--platform", default=None,
                    help="Optional pip --platform for cross-download (e.g., win_amd64). Default: current platform.")
    ap.add_argument("--python-version", default=None,
                    help="Optional pip --python-version (e.g., 310). Default: current Python.")
    ap.add_argument("--implementation", default=None,
                    help="Optional pip --implementation (e.g., cp). Default: auto.")
    args = ap.parse_args()

    ensure_dir(args.out)
    ensure_dir(args.models_dir)

    # Make pip a bit quieter & deterministic
    os.environ.setdefault("PIP_DISABLE_PIP_VERSION_CHECK", "1")

    # 1) General pass: download requirements
    dl_cmd = pip("download", "-r", str(args.requirements), "-d", str(args.out), "--only-binary=:all:", "--prefer-binary")
    if args.platform:
        dl_cmd += ["--platform", args.platform]
    if args.python_version:
        dl_cmd += ["--python-version", args.python_version]
    if args.implementation:
        dl_cmd += ["--implementation", args.implementation]

    print("\n=== STEP 1: Downloading requirements into wheelhouse ===")
    run(dl_cmd)

    # 2) Torch wheels from specific channel (if missing)
    print("\n=== STEP 2: Ensuring Torch wheels are present ===")
    ensure_torch_wheels(args.out, args.torch_channel, args.torch_extras)

    # 3) Ensure llama-cpp-python wheel exists (download or build)
    print("\n=== STEP 3: Ensuring llama-cpp-python wheel is present ===")
    ensure_llama_cpp_wheel(args.out, args.build_llama)

    # 4) Download the model
    print("\n=== STEP 4: Downloading model ===")
    download_model(args.model_repo, args.models_dir)

    # 5) Summary
    print("\n=== DONE ===")
    print(f"Wheelhouse: {args.out.resolve()}")
    print(f"Model dir:  {(args.models_dir / normalize_repo_id(args.model_repo)).resolve()}")
    print("\nOffline install example:")
    print(f"  pip install --no-index --find-links={args.out} -r {args.requirements}")

if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Command failed with exit code {e.returncode}")
        sys.exit(e.returncode)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)

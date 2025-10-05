# Offline Installation Guide

This guide explains how to set up the Company Intelligence Query Engine on a machine with restricted or no internet connectivity.

## Overview

The system requires several Python packages that can be pre-downloaded and installed offline.

---

## Step 1: Download Dependencies (On Online Machine)

### Create Package Directory
```bash
mkdir packages
```

### Download All Dependencies
```bash
pip download -r requirements.txt -d packages/
```

This will download:
- pandas, numpy (data processing)
- sentence-transformers, torch, transformers (semantic search)
- llama-cpp-python (LLM support)
- All their dependencies (~3-4 GB total)

### Download Sentence-Transformer Model (Important!)
```bash
python download_model.py
```

This creates: `models/all-MiniLM-L6-v2/` directory with the embedding model.

---

## Step 2: Transfer to Offline Machine

### Copy These Directories/Files:
```
company_intel_bundle/
├── packages/              # Downloaded Python packages
├── models/                # Pre-downloaded embedding model
├── requirements.txt
├── full_engine_query.py
├── test_queries.py
├── etl/
├── views/
├── inputs/
└── README_USAGE.md
```

### Transfer Qwen LLM Model:
Copy your Qwen model file:
```
D:\CBDPIT\TEMP6\Qwen2.5-3B-Instruct-Q8_0.gguf
```

---

## Step 3: Install on Offline Machine

### Install Python Packages (Offline)
```bash
pip install --no-index --find-links=packages/ -r requirements.txt
```

### Verify Installation
```bash
python -c "import pandas, numpy, sentence_transformers, llama_cpp; print('✅ All packages installed')"
```

---

## Step 4: Verify Model Files

### Check Embedding Model:
```bash
# Should exist:
models/all-MiniLM-L6-v2/
├── config.json
├── pytorch_model.bin
├── tokenizer.json
└── ...
```

### Check Qwen LLM:
```bash
# Should exist and be ~3GB:
D:\CBDPIT\TEMP6\Qwen2.5-3B-Instruct-Q8_0.gguf
```

---

## Step 5: Configure for Offline Use

### Update Model Path in Code:
The system automatically uses local models directory by default.

**Default Configuration** (already set in code):
- Embedding model: `models/all-MiniLM-L6-v2` (local path)
- All files now default to reading from the local models directory
- No code changes needed for offline operation

Example usage:
```python
# In full_engine_query.py, app_rag_chat.py, etl/llm_classifier.py, tests/test_queries.py
# These files already use the local models directory by default:
engine = EnhancedQueryEngine(
    views_dir="views",
    model_name="models/all-MiniLM-L6-v2",  # Local path (DEFAULT)
    llm_model_path=r"D:\CBDPIT\TEMP6\Qwen2.5-3B-Instruct-Q8_0.gguf"
)
```

---

## Step 6: Test Offline Setup

### Build Views (No Internet Required)
```bash
python etl\build_views_pandas.py --in inputs --out views
```

### Build Index (Uses Local Model)
```bash
python full_engine_query.py index --views views --model models/all-MiniLM-L6-v2
```

### Run Test Queries (Fully Offline)
```bash
python test_queries.py
```

---

## Quick Setup Script

### For Online Machine (download_all.bat):
```bat
@echo off
echo Downloading all dependencies for offline installation...

echo.
echo Step 1: Creating packages directory...
mkdir packages 2>nul

echo.
echo Step 2: Downloading Python packages...
pip download -r requirements.txt -d packages/

echo.
echo Step 3: Downloading embedding model...
python download_model.py

echo.
echo Step 4: Verifying downloads...
dir packages
dir models

echo.
echo ✅ Download complete!
echo.
echo Next steps:
echo 1. Copy 'packages' and 'models' folders to offline machine
echo 2. Copy Qwen LLM model to offline machine
echo 3. Run: pip install --no-index --find-links=packages/ -r requirements.txt
pause
```

### For Offline Machine (install_offline.bat):
```bat
@echo off
echo Installing packages for offline use...

echo.
echo Installing Python dependencies...
pip install --no-index --find-links=packages/ -r requirements.txt

echo.
echo Verifying installation...
python -c "import pandas, numpy, sentence_transformers; print('✅ Core packages OK')"
python -c "import llama_cpp; print('✅ LLM package OK')"

echo.
echo Testing system...
python full_engine_query.py index --views views --model models/all-MiniLM-L6-v2

echo.
echo ✅ Installation complete!
echo.
echo You can now run queries offline:
echo   python test_queries.py
pause
```

---

## Package Sizes (Approximate)

| Package | Size | Purpose |
|---------|------|---------|
| pandas | ~50 MB | Data processing |
| numpy | ~25 MB | Numerical operations |
| torch | ~800 MB | PyTorch framework |
| sentence-transformers | ~10 MB | Semantic search |
| transformers | ~300 MB | Model loading |
| llama-cpp-python | ~50 MB | LLM inference |
| Dependencies | ~1 GB | Supporting packages |
| **Total** | **~2.2 GB** | Python packages |
| Embedding Model | ~100 MB | all-MiniLM-L6-v2 |
| Qwen LLM | ~3 GB | Qwen2.5-3B-Instruct |
| **Grand Total** | **~5.3 GB** | Everything |

---

## Troubleshooting

### Issue 1: "No module named 'sentence_transformers'"
**Solution**: Ensure packages were installed:
```bash
pip install --no-index --find-links=packages/ sentence-transformers
```

### Issue 2: "Model not found"
**Solution**: Check model path:
```bash
# Should see model files:
dir models\all-MiniLM-L6-v2
```

### Issue 3: "llama-cpp-python not found"
**Solution**: This package needs compilation. On offline machine:
```bash
# Pre-download compiled wheel for your platform
pip download llama-cpp-python==0.2.0 --platform win_amd64 --python-version 311
```

### Issue 4: Qwen LLM loading error
**Check**:
1. File exists and is ~3 GB
2. Path is correct in test_queries.py
3. Sufficient RAM (~4 GB free)

---

## Pre-Downloaded Package Checklist

Before transferring to offline machine, verify you have:

- [ ] `packages/` directory with all .whl files
- [ ] `models/all-MiniLM-L6-v2/` directory with model files
- [ ] `Qwen2.5-3B-Instruct-Q8_0.gguf` (3 GB LLM file)
- [ ] `requirements.txt`
- [ ] All Python scripts
- [ ] `inputs/` and `views/` data directories

---

## Testing Offline Mode

```bash
# 1. Disconnect from internet or use firewall to block Python

# 2. Try building index
python full_engine_query.py index --views views --model models/all-MiniLM-L6-v2

# 3. Try a query
python full_engine_query.py query --views views --ask "defence companies" --model models/all-MiniLM-L6-v2

# 4. If successful, you're fully offline capable!
```

---

## Notes

1. **torch**: Large package (~800 MB), downloads automatically during first install
2. **Qwen LLM**: Must be copied manually (3 GB file)
3. **Embedding Model**: Downloads automatically on first use, OR pre-download with script
4. **Updates**: To update packages, repeat Step 1 on online machine

---

## Summary

**For Offline Operation**:
1. ✅ Download packages: `pip download -r requirements.txt -d packages/`
2. ✅ Download model: `python download_model.py`
3. ✅ Copy Qwen LLM
4. ✅ Transfer to offline machine
5. ✅ Install: `pip install --no-index --find-links=packages/ -r requirements.txt`
6. ✅ Test: `python test_queries.py`

**Total Transfer Size**: ~5.3 GB
**Installation Time**: ~10 minutes
**After Setup**: Fully offline capable! ✅

# Company Intelligence Query Engine - User Guide

## Overview

An AI-powered query engine for searching and analyzing company data using semantic search and Qwen LLM for natural language responses.

## Features

✅ **Natural Language Queries** - Ask questions in plain English
✅ **Qwen LLM Integration** - AI-generated contextual answers
✅ **Semantic Search** - Finds relevant companies intelligently
✅ **CSV-Based Filtering** - Fast structured queries
✅ **Industry Inference** - Auto-detects industry domains from products
✅ **Multi-Criteria Search** - Defence, MSME, Location, Industry domain

---

## Prerequisites

### Required:
- Python 3.8+
- Qwen2.5-3B-Instruct LLM model at: `D:\CBDPIT\TEMP6\Qwen2.5-3B-Instruct-Q8_0.gguf`

### Install Dependencies:
```bash
pip install pandas numpy sentence-transformers llama-cpp-python
```

---

## Quick Start (3 Steps)

### Step 1: Build Enriched Data Views
```bash
python etl\build_views_pandas.py --in inputs --out views
```
**What it does**: 
- Enriches company data with industry inference
- Creates aggregated views
- Generates CompanyDetailEnriched.csv

**Output**: 
```
✅ CompanyDetailEnriched.csv created with 15692 companies
   ℹ️  Inferred industry domain for 1669 companies from their products
```

---

### Step 2: Build Semantic Index
```bash
python full_engine_query.py index --views views
```
**What it does**:
- Creates embeddings for semantic search
- Stores in `views/.sem_index/`

**Note**: This happens automatically on first query, but building it upfront is faster.

---

### Step 3: Run Queries (with Qwen LLM)

#### Run Test Suite (Recommended)
```bash
python test_queries.py
```
**Runs 3 example queries**:
1. List all defence startups
2. List of MSME in India  
3. Companies based in Bhopal

**Output Format**:
```
🔍 Query 1: Defence Startups
Question: List all defence startups

⏳ Processing query...

🤖 QWEN LLM ANSWER (⏱️ 128.98s)
Based on the provided data, here are the defense startups listed:
1. BHARAT DYNAMICS LIMITED
2. BHARAT FORGE LTD
...

📊 TOP 10 MATCHING COMPANIES
 1. BHARAT DYNAMICS LIMITED
    📍 Telangana
    🏭 Defence & Aerospace
    
✅ Total found: 26 companies
```

#### Run Individual Queries
```bash
# With LLM (Default - Recommended)
python full_engine_query.py query --views views --ask "companies in electrical domain" --llm D:\CBDPIT\TEMP6\Qwen2.5-3B-Instruct-Q8_0.gguf

# Shorter alias (if LLM path is too long to type)
set LLM_PATH=D:\CBDPIT\TEMP6\Qwen2.5-3B-Instruct-Q8_0.gguf
python full_engine_query.py query --views views --ask "companies in electrical domain" --llm %LLM_PATH%
```

---

## Query Examples

### 1. Industry-Based Queries
```bash
# Electrical companies
python full_engine_query.py query --views views --ask "companies in electrical domain" --llm D:\CBDPIT\TEMP6\Qwen2.5-3B-Instruct-Q8_0.gguf

# Defence companies
python full_engine_query.py query --views views --ask "List all defence startups" --llm D:\CBDPIT\TEMP6\Qwen2.5-3B-Instruct-Q8_0.gguf

# IT companies
python full_engine_query.py query --views views --ask "software companies" --llm D:\CBDPIT\TEMP6\Qwen2.5-3B-Instruct-Q8_0.gguf
```

### 2. Location-Based Queries
```bash
# Companies in Bhopal
python full_engine_query.py query --views views --ask "Companies based in Bhopal" --llm D:\CBDPIT\TEMP6\Qwen2.5-3B-Instruct-Q8_0.gguf

# Companies in Pune
python full_engine_query.py query --views views --ask "companies in Pune" --llm D:\CBDPIT\TEMP6\Qwen2.5-3B-Instruct-Q8_0.gguf

# Maharashtra companies
python full_engine_query.py query --views views --ask "companies in Maharashtra" --llm D:\CBDPIT\TEMP6\Qwen2.5-3B-Instruct-Q8_0.gguf
```

### 3. MSME Queries
```bash
# All MSME companies
python full_engine_query.py query --views views --ask "List of MSME in India" --llm D:\CBDPIT\TEMP6\Qwen2.5-3B-Instruct-Q8_0.gguf

# Micro enterprises
python full_engine_query.py query --views views --ask "micro enterprises" --llm D:\CBDPIT\TEMP6\Qwen2.5-3B-Instruct-Q8_0.gguf

# Small companies in Bangalore
python full_engine_query.py query --views views --ask "small companies in Bangalore" --llm D:\CBDPIT\TEMP6\Qwen2.5-3B-Instruct-Q8_0.gguf
```

### 4. Company Attribute Queries
```bash
# Industry of specific company
python full_engine_query.py query --views views --ask "Industry type of FLONEX OIL TECHNOLOGIES PRIVATE LIMITED" --llm D:\CBDPIT\TEMP6\Qwen2.5-3B-Instruct-Q8_0.gguf

# Company location
python full_engine_query.py query --views views --ask "Where is BHARAT DYNAMICS located" --llm D:\CBDPIT\TEMP6\Qwen2.5-3B-Instruct-Q8_0.gguf

# Company products
python full_engine_query.py query --views views --ask "What products does APOLLO MICRO SYSTEMS make" --llm D:\CBDPIT\TEMP6\Qwen2.5-3B-Instruct-Q8_0.gguf
```

### 5. Combined Queries
```bash
# Defence companies in specific location
python full_engine_query.py query --views views --ask "defence companies in Bangalore" --llm D:\CBDPIT\TEMP6\Qwen2.5-3B-Instruct-Q8_0.gguf

# Electrical companies in Maharashtra
python full_engine_query.py query --views views --ask "electrical companies in Maharashtra" --llm D:\CBDPIT\TEMP6\Qwen2.5-3B-Instruct-Q8_0.gguf

# MSME defence suppliers
python full_engine_query.py query --views views --ask "small defence suppliers" --llm D:\CBDPIT\TEMP6\Qwen2.5-3B-Instruct-Q8_0.gguf
```

### 6. Export Results
```bash
# Export to ZIP file
python full_engine_query.py query --views views --ask "defence companies" --llm D:\CBDPIT\TEMP6\Qwen2.5-3B-Instruct-Q8_0.gguf --zip-out defence_results.zip
```

---

## Command Reference

### Full Command Structure
```bash
python full_engine_query.py query \
  --views <path-to-views> \
  --ask "<your-question>" \
  --llm <path-to-llm-model> \
  [--top-k <number>] \
  [--zip-out <output.zip>]
```

### Parameters:
- `--views` : Path to views directory (required)
- `--ask` : Your natural language question (required)
- `--llm` : Path to Qwen LLM model (required for AI answers)
- `--top-k` : Number of results to return (default: 20)
- `--zip-out` : Export results to ZIP file (optional)

---

## Data Files Structure

```
company_intel_bundle/
├── inputs/                              # Source data
│   ├── dbo.CompanyMaster.csv
│   ├── dbo.CompanyProducts.csv
│   └── ... (other source files)
│
├── views/                               # Generated views
│   ├── CompanyDetailEnriched.csv       # ⭐ Main enriched data
│   ├── Products.csv
│   ├── Facilities.csv
│   ├── Certification.csv
│   ├── TurnOver.csv
│   └── .sem_index/                     # Semantic embeddings
│
├── etl/
│   └── build_views_pandas.py           # Data enrichment script
│
├── full_engine_query.py                # Main query engine
├── test_queries.py                     # Test suite with LLM
└── README_USAGE.md                     # This file
```

---

## Performance Metrics

### Query Times (with Qwen LLM on CPU):
- **First query**: ~2-3 minutes (includes model loading)
- **Subsequent queries**: ~1-2 minutes (model cached)
- **CSV filtering only**: <1 second
- **Semantic search only**: 1-2 seconds

### Memory Usage:
- **Qwen LLM**: ~3.5 GB RAM
- **Embeddings**: ~400 MB RAM
- **Total**: ~4 GB RAM recommended

---

## Troubleshooting

### Issue 1: "llama.cpp not found"
**Solution**:
```bash
pip install llama-cpp-python
```

### Issue 2: LLM loading errors
**Check**:
1. LLM file exists at: `D:\CBDPIT\TEMP6\Qwen2.5-3B-Instruct-Q8_0.gguf`
2. File is not corrupted (should be ~3 GB)
3. Sufficient RAM available (~4 GB)

### Issue 3: "Semantic index not found"
**Solution**:
```bash
python full_engine_query.py index --views views --force
```

### Issue 4: Slow queries
**Tips**:
1. First query is always slower (model loading)
2. Use `--top-k 10` for faster results
3. CSV filters (defence, MSME, location) are instant
4. Consider GPU acceleration for llama-cpp-python

---

## Workflow Tips

### Daily Usage:
```bash
# Just run queries - everything auto-builds as needed
python full_engine_query.py query --views views --ask "your question" --llm D:\CBDPIT\TEMP6\Qwen2.5-3B-Instruct-Q8_0.gguf
```

### After Data Updates:
```bash
# 1. Rebuild enriched views
python etl\build_views_pandas.py --in inputs --out views

# 2. Rebuild semantic index
python full_engine_query.py index --views views --force

# 3. Run queries
python full_engine_query.py query --views views --ask "your question" --llm D:\CBDPIT\TEMP6\Qwen2.5-3B-Instruct-Q8_0.gguf
```

### Testing Changes:
```bash
# Run comprehensive test suite
python test_queries.py
```

---

## Example Session

```bash
# Terminal session example

# Step 1: Build views (one-time)
PS> python etl\build_views_pandas.py --in inputs --out views
Building enriched company view with industry inference...
✅ CompanyDetailEnriched.csv created with 15692 companies
   ℹ️  Inferred industry domain for 1669 companies from their products

# Step 2: Run a query
PS> python full_engine_query.py query --views views --ask "defence companies in Pune" --llm D:\CBDPIT\TEMP6\Qwen2.5-3B-Instruct-Q8_0.gguf

🔧 Building semantic index from views...
✅ Index built: 15692 companies × 384 dims

=== ANSWER ===
Based on the search results, I found 8 defence and aerospace companies in 
Pune and Maharashtra region. The major players include:

1. BHARAT FORGE LTD (Maharashtra) - Leading defence equipment manufacturer
2. KALYANI STRATEGIC SYSTEMS LIMITED (Maharashtra) - Defence systems
3. ACCU-SIZE GAUGES AND TOOLS PRIVATE LIMITED (Maharashtra)
...

# Results displayed with company names, locations, and industry domains
```

---

## Key Features Explained

### 1. Industry Inference
- Automatically detects industry domains from product names
- Example: "hydraulic oils" → "Chemical & Petroleum Products"
- Covers 1,669 companies that were missing industry data

### 2. Semantic Search
- Uses sentence-transformers embeddings
- Finds relevant companies even with fuzzy queries
- Example: "electrical" matches "Electronics & Electrical", "power systems", etc.

### 3. CSV-Based Filtering
- Instant filtering for structured queries
- Defence: filters by industry domain
- MSME: searches company names for "Micro", "Small", "Medium"
- Location: searches City, State, Address fields

### 4. Qwen LLM Integration
- Generates natural language answers
- Contextual and factual responses
- Stays grounded in retrieved data

---

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review example queries
3. Run test suite: `python test_queries.py`

---

## Quick Command Cheat Sheet

```bash
# Build data
python etl\build_views_pandas.py --in inputs --out views

# Build index
python full_engine_query.py index --views views

# Query with LLM (always use this)
python full_engine_query.py query --views views --ask "your question" --llm D:\CBDPIT\TEMP6\Qwen2.5-3B-Instruct-Q8_0.gguf

# Test suite
python test_queries.py

# Force rebuild index
python full_engine_query.py index --views views --force
```

---

**Ready to use!** Start with `python test_queries.py` to see the system in action.

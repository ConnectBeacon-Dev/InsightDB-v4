#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
enhanced_query_engine.py - WITH LOCATION-AWARE MATCHING
"""

from __future__ import annotations

import os, re, json, argparse, hashlib, io, zipfile
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

import pandas as pd

# Import the new intent handler
try:
    from .intent_handler import IntentHandler
    INTENT_HANDLER_AVAILABLE = True
except ImportError:
    try:
        from intent_handler import IntentHandler
        INTENT_HANDLER_AVAILABLE = True
    except ImportError:
        INTENT_HANDLER_AVAILABLE = False
        print("  IntentHandler not available, using legacy intent detection")

# Optional dependencies
TRANSFORMERS_AVAILABLE = False
try:
    from sentence_transformers import SentenceTransformer
    TRANSFORMERS_AVAILABLE = True
except Exception:
    pass

try:
    import numpy as np
except Exception:
    np = None

# BM25 support
try:
    from rank_bm25 import BM25Okapi
    HAVE_BM25 = True
except:
    HAVE_BM25 = False


# ============================================================================
# DEPENDENCY CHECKING
# ============================================================================

def check_dependencies(verbose: bool = True) -> dict:
    """
    Check system dependencies and report status.
    Returns dict with status and warnings.
    """
    status = {
        "all_ok": True,
        "critical_missing": [],
        "optional_missing": [],
        "warnings": []
    }
    
    # Critical dependencies
    if np is None:
        status["critical_missing"].append("numpy")
        status["all_ok"] = False
    
    try:
        import pandas
    except ImportError:
        status["critical_missing"].append("pandas")
        status["all_ok"] = False
    
    # Important but not critical
    if not TRANSFORMERS_AVAILABLE:
        status["optional_missing"].append("sentence-transformers")
        status["warnings"].append("WARNING: sentence-transformers not installed - semantic search DISABLED, using keyword fallback")
    
    if not HAVE_BM25:
        status["optional_missing"].append("rank-bm25")
        status["warnings"].append("WARNING: rank-bm25 not installed - keyword scoring may be less accurate")
    
    if not INTENT_HANDLER_AVAILABLE:
        status["optional_missing"].append("intent_handler")
        status["warnings"].append("WARNING: IntentHandler not available - using legacy intent detection")
    
    # Print report if verbose
    if verbose and (status["critical_missing"] or status["warnings"]):
        print("\n" + "="*70)
        print("DEPENDENCY STATUS CHECK")
        print("="*70)
        
        if status["critical_missing"]:
            print("\nCRITICAL DEPENDENCIES MISSING:")
            for dep in status["critical_missing"]:
                print(f"   - {dep}")
            print("\n   System will NOT work properly!")
            print("   Run: pip install -r requirements.txt")
        
        if status["warnings"]:
            print("\nWARNINGS:")
            for warning in status["warnings"]:
                print(f"   {warning}")
        
        if not status["critical_missing"] and status["optional_missing"]:
            print("\nOK: Core functionality available (with degraded features)")
        elif not status["critical_missing"]:
            print("\nOK: All dependencies installed")
        
        print("="*70 + "\n")
    
    # Raise error if critical dependencies missing
    if status["critical_missing"]:
        raise RuntimeError(
            f"Critical dependencies missing: {', '.join(status['critical_missing'])}. "
            f"Run: pip install -r requirements.txt"
        )
    
    return status


# ============================================================================
# MODULE-LEVEL CONSTANTS AND HELPER FUNCTIONS
# ============================================================================

# Common Indian locations (canonical names) for extraction
INDIAN_LOCATIONS = {
    'maharashtra', 'gujarat', 'delhi', 'mumbai', 'bangalore', 'bengaluru',
    'chennai', 'hyderabad', 'kolkata', 'pune', 'ahmedabad', 'kerala',
    'karnataka', 'tamil nadu', 'telangana', 'rajasthan', 'punjab', 'haryana',
    'uttar pradesh', 'madhya pradesh', 'andhra pradesh', 'west bengal',
    'odisha', 'uttarakhand'
}

# Aliases and common misspellings mapped to canonical names
COMMON_LOCATION_ALIASES = {
    # Maharashtra variants
    'maharastra': 'maharashtra',
    'maharashra': 'maharashtra',
    'maharashatra': 'maharashtra',
    'maharashstra': 'maharashtra',
    'mh': 'maharashtra',
    # Gujarat
    'gujrat': 'gujarat',
    # Tamil Nadu
    'tamilnadu': 'tamil nadu',
    # Uttar Pradesh / Madhya Pradesh shorthand
    'up': 'uttar pradesh',
    'mp': 'madhya pradesh',
}

def _extract_location(text: str) -> Optional[str]:
    """Extract location from text if present (robust to misspellings and multi-word locations)."""
    s = text.lower().strip()
    s = re.sub(r"[^\w\s\-&/]", " ", s)
    s = re.sub(r"\s+", " ", s)

    # 1) Direct alias hits
    for alias, canonical in COMMON_LOCATION_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", s):
            return canonical

    # 2) Direct canonical hits, prefer longer names first (e.g., 'tamil nadu' before 'tamil')
    for loc in sorted(INDIAN_LOCATIONS, key=len, reverse=True):
        if re.search(rf"\b{re.escape(loc)}\b", s):
            return loc

    # 3) Fallback: fuzzy match on individual tokens against canonical set
    try:
        import difflib
        tokens = set(s.split())
        for tok in tokens:
            # Check alias fuzzy match first
            alias_match = difflib.get_close_matches(tok, COMMON_LOCATION_ALIASES.keys(), n=1, cutoff=0.85)
            if alias_match:
                return COMMON_LOCATION_ALIASES[alias_match[0]]
            # Then canonical names (single tokens only)
            canon_match = difflib.get_close_matches(tok, {w for w in INDIAN_LOCATIONS if ' ' not in w}, n=1, cutoff=0.88)
            if canon_match:
                return canon_match[0]
    except Exception:
        pass

    return None

def _remove_location(text: str, location: Optional[str] = None) -> str:
    """Remove location tokens from text."""
    if location is None:
        location = _extract_location(text)
    if location:
        text = re.sub(r'\b' + re.escape(location) + r'\b', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s+', ' ', text).strip()
    return text

def _minmax_normalize(scores: Dict[str, float]) -> Dict[str, float]:
    """Min-max normalize scores to 0-1 range."""
    if not scores or np is None:
        return scores
    vals = np.array(list(scores.values()), dtype=float)
    vmin, vmax = float(vals.min()), float(vals.max())
    if vmax == vmin:
        return {k: 0.0 for k in scores}
    return {k: (v - vmin) / (vmax - vmin) for k, v in scores.items()}


# ============================================================================
# CORE ENGINE CLASS
# ============================================================================

class EnhancedQueryEngine:
    def __init__(
        self,
        inputs_dir: str = "inputs",
        views_dir: str = "views",
        model_name: str = "models/all-MiniLM-L6-v2",
        llm_model_path: Optional[str] = None,
        log_file: str = "query_log.jsonl",
        intents_file: str = "intents_reference.json",
        check_deps: bool = True
    ):
        # Check dependencies on first initialization
        if check_deps:
            self.dependency_status = check_dependencies(verbose=True)
        
        self.inputs_dir = Path(inputs_dir)
        self.views_dir  = Path(views_dir)
        self.index_dir  = self.views_dir / ".sem_index"
        self.index_dir.mkdir(parents=True, exist_ok=True)
        
        self.log_file = Path(log_file)

        self._embedder_name = model_name
        self._embedder: Optional["SentenceTransformer"] = None
        
        # Initialize BM25 cache
        self._bm25 = None
        self._bm25_company_ids = None
        
        # Load intent patterns
        self.intents = self._load_intents(intents_file)

        # Optional LLM
        self.llm = None
        if llm_model_path:
            try:
                from llama_cpp import Llama
                self.llm = Llama(model_path=llm_model_path, n_ctx=4096, n_threads=max(1, os.cpu_count() or 4))
                print(" LLM loaded for optional answer synthesis.")
            except Exception as e:
                print(f"  Could not load LLM: {e}")
    
    def _load_intents(self, intents_file: str) -> Dict[str, Any]:
        """Load intent patterns from JSON reference file"""
        try:
            intents_path = Path(intents_file)
            if intents_path.exists():
                with open(intents_path, 'r', encoding='utf-8') as f:
                    intents = json.load(f)
                print(f" Loaded intent patterns from {intents_file}")
                return intents
            else:
                print(f"  Intent reference file {intents_file} not found, using default patterns")
                return {}
        except Exception as e:
            print(f"  Error loading intent patterns: {e}")
            return {}

    # ==================== BUILD & QUERY ====================

    def build_semantic_index(self, force: bool = False) -> None:
        """Build + persist embeddings over ALL views."""
        if not TRANSFORMERS_AVAILABLE or np is None:
            print("  sentence-transformers / numpy not available.")
            return

        meta_info = self._collect_view_files()
        content_hash = self._hash_views(meta_info["files_present"])
        meta_path = self.index_dir / "meta.json"
        emb_path  = self.index_dir / "embeddings.npy"
        idx_path  = self.index_dir / "doc_index.csv"

        if meta_path.exists() and emb_path.exists() and idx_path.exists() and not force:
            prev = json.loads(meta_path.read_text(encoding="utf-8"))
            if prev.get("content_hash") == content_hash:
                print(" Semantic index already up-to-date.")
                return

        print(" Building semantic index from views...")
        doc_index = self._build_company_corpus(meta_info)
        texts = doc_index["search_text"].tolist()

        self._ensure_embedder()
        assert self._embedder is not None
        emb = self._embedder.encode(texts, show_progress_bar=True, convert_to_numpy=True).astype("float32")
        # Row-normalize
        norms = np.linalg.norm(emb, axis=1, keepdims=True) + 1e-8
        emb = emb / norms

        # Persist
        np.save(emb_path, emb)
        doc_index.to_csv(idx_path, index=False)
        meta_out = {
            "content_hash": content_hash,
            "model_name": self._embedder_name,
            "rows": int(emb.shape[0]),
            "dims": int(emb.shape[1]),
            "source_files": meta_info["files_present"],
        }
        meta_path.write_text(json.dumps(meta_out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f" Index built: {emb.shape[0]} companies × {emb.shape[1]} dims")

    def semantic_search_companies(self, query: str, top_k: int = 20) -> pd.DataFrame:
        """
        Search with location as a filter (Option 4: Filter-based approach).
        Location in query is treated as a hard filter, not a scoring factor.
        """
        if not TRANSFORMERS_AVAILABLE or np is None:
            print("  Semantic search unavailable; fallback to keyword.")
            return self._keyword_search(query)

        self.build_semantic_index(force=False)

        E, doc_index = self._load_index()
        if E is None or doc_index is None or E.shape[0] == 0:
            print("  Index missing/empty; fallback to keyword.")
            return self._keyword_search(query)

        # Extract location from query - treat as filter
        # BUT: Don't extract location if query is asking about a specific company
        # (e.g., "Contact of MADHYA PRADESH BHARAT AGRO" - "MADHYA PRADESH" is part of company name)
        query_lower = query.lower()
        is_company_specific_query = any(keyword in query_lower for keyword in [
            ' of ', ' for ', 'details of', 'address of', 'contact of', 'pan of', 
            'cin of', 'gst of', 'email of', 'phone of', 'website of'
        ])
        
        if is_company_specific_query:
            # Don't extract location - it might be part of the company name
            query_location = None
            query_content = query
        else:
            # Extract location for filtering
            query_location = _extract_location(query)
            query_content = _remove_location(query, query_location)
        
        print(f"\n[DEBUG] semantic_search_companies called")
        print(f"[DEBUG] Company-specific query: {is_company_specific_query}")
        print(f"[DEBUG] Extracted location: {query_location}")
        print(f"[DEBUG] Content query: '{query_content}'")
        
        # Check if query mentions R&D/Test facilities - if so, we'll need to search more candidates
        query_lower = query.lower()
        rd_keywords = ['r&d', 'r & d', 'research and development', 'research & development', 'r&d facility', 'r&d facilities']
        test_keywords = [
            'test facility', 'test facilities', 'testing facility', 'testing facilities',
            'test lab', 'test labs', 'testing lab', 'testing labs',
            'having test', 'with test', 'test capabilit'  # Partial matches for broader detection
        ]
        has_rd_keyword = any(keyword in query_lower for keyword in rd_keywords)
        has_test_keyword = any(keyword in query_lower for keyword in test_keywords)
        
        # Debug output
        if has_rd_keyword:
            matched_rd = [kw for kw in rd_keywords if kw in query_lower]
            print(f"  R&D keywords detected: {matched_rd}")
        if has_test_keyword:
            matched_test = [kw for kw in test_keywords if kw in query_lower]
            print(f"  Test facility keywords detected: {matched_test}")
        
        # Expand search space when filtering by facilities (since many will be filtered out)
        # Use larger multiplier to ensure we find all companies with the specified facilities
        search_multiplier = 50 if (has_rd_keyword or has_test_keyword) else 1
        expanded_top_k = min(top_k * search_multiplier, 1000)  # Cap at 1000 to avoid performance issues
        
        if query_location:
            print(f"  Location filter: {query_location}, Content query: '{query_content}'")
        else:
            print(f"  No location detected in query, searching all locations")
        
        if has_rd_keyword or has_test_keyword:
            print(f"  R&D/Test facility query detected - expanding search to top {expanded_top_k} candidates")
            print(f"  has_rd_keyword={has_rd_keyword}, has_test_keyword={has_test_keyword}")
        
        # Load company details for location filtering
        comp = self._load_company_detail()
        comp["Id"] = comp["Id"].astype(str)
        
        # OPTION 4: Apply location filter FIRST if location specified
        if query_location:
            # Filter companies by location
            location_mask = pd.Series(False, index=comp.index)
            print(f"[DEBUG] Total companies before filter: {len(comp)}")
            
            for col in ["City", "State", "Address"]:
                if col in comp.columns:
                    # Direct string matching first (more reliable than extraction)
                    direct_match = comp[col].str.lower().str.contains(query_location, case=False, na=False, regex=False)
                    matches_this_col = direct_match.sum()
                    print(f"[DEBUG] {col} direct matches: {matches_this_col}")
                    location_mask |= direct_match
                    
                    # Also try extraction-based matching for normalized comparison
                    comp_locations = comp[col].apply(lambda x: _extract_location(str(x)) if pd.notna(x) else None)
                    extraction_matches = (comp_locations == query_location)
                    matches_extraction = extraction_matches.sum()
                    print(f"[DEBUG] {col} extraction matches: {matches_extraction}")
                    location_mask |= extraction_matches
            
            filtered_comp = comp[location_mask]
            
            if filtered_comp.empty:
                print(f"  No companies found in location: {query_location}")
                return pd.DataFrame()
            
            print(f"  Filtered to {len(filtered_comp)} companies in {query_location}")
            
            # Filter doc_index and embeddings to only include companies in the location
            filtered_company_ids = set(filtered_comp["Id"].astype(str))
            doc_mask = doc_index["CompanyId"].astype(str).isin(filtered_company_ids)
            doc_index_filtered = doc_index[doc_mask].copy()
            E_filtered = E[doc_mask.values] if E is not None else None
            
            if doc_index_filtered.empty or E_filtered is None or E_filtered.shape[0] == 0:
                print(f"  No indexed companies in location: {query_location}")
                return pd.DataFrame()
        else:
            # No location filter - use full dataset
            doc_index_filtered = doc_index
            E_filtered = E

        # ---- SEMANTIC SCORING (on filtered dataset) ----
        self._ensure_embedder()
        qv = self._embedder.encode([query_content], show_progress_bar=False, convert_to_numpy=True)[0].astype("float32")
        qv = qv / (np.linalg.norm(qv) + 1e-8)
        semantic_sims = E_filtered @ qv

        # ---- KEYWORD SCORING (BM25 on filtered dataset) ----
        # Rebuild BM25 on filtered corpus to ensure accurate scoring
        keyword_scores = self._get_keyword_scores_filtered(query_content, doc_index_filtered)

        # Combine scores using RAW values (not normalized) to preserve absolute relevance
        semantic_dict = {doc_index_filtered.iloc[i]["CompanyId"]: float(semantic_sims[i]) for i in range(len(doc_index_filtered))}
        
        # Keep raw scores for filtering, but also compute normalized for display
        semantic_norm = _minmax_normalize(semantic_dict)
        keyword_norm = _minmax_normalize(keyword_scores)
        
        SEMANTIC_WEIGHT = 0.7
        KEYWORD_WEIGHT = 0.3
        
        # Use RAW scores for ranking to maintain absolute relevance threshold
        combined_scores = {}
        for company_id in semantic_dict:
            # Raw semantic similarity (cosine similarity, already 0-1 range)
            sem_score_raw = semantic_dict.get(company_id, 0.0)
            # Keyword scores need normalization since BM25 range varies
            kw_score_norm = keyword_norm.get(company_id, 0.0)
            # Combine: use raw semantic + normalized keyword
            combined_scores[company_id] = SEMANTIC_WEIGHT * sem_score_raw + KEYWORD_WEIGHT * kw_score_norm
        
        # Get top candidates based on content relevance
        # For facility queries, we need a larger candidate pool since we'll filter by actual facility data
        # For other queries, use top_k
        if has_rd_keyword or has_test_keyword:
            # For facility queries: First, get ALL companies that have the specified facilities
            # Then rank them by semantic relevance
            # This ensures we don't miss companies just because their semantic score is low
            candidate_limit = len(combined_scores)  # Include all companies initially
            print(f"  Facility query detected - will search all {candidate_limit} companies then filter by facilities")
        else:
            # For non-facility queries: use top candidates based on semantic relevance
            candidate_limit = expanded_top_k
        
        sorted_ids = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)[:candidate_limit]
        
        # Build results DataFrame
        candidate_ids = [cid for cid, _ in sorted_ids]
        score_map = dict(sorted_ids)
        
        top = doc_index_filtered[doc_index_filtered["CompanyId"].isin(candidate_ids)].copy()
        top["similarity_score"] = top["CompanyId"].map(score_map)
        top["semantic_score"] = top["CompanyId"].map(semantic_dict)  # Raw semantic score
        top["keyword_score"] = top["CompanyId"].map(keyword_norm)   # Normalized keyword score

        # Join with CompanyDetail for full info
        top["CompanyId"] = top["CompanyId"].astype(str)
        res = top.merge(comp, left_on="CompanyId", right_on="Id", how="left")
        
        if "CompanyName_y" in res.columns:
            res["CompanyName"] = res["CompanyName_y"].fillna(res.get("CompanyName_x", ""))
            res = res.drop(columns=["CompanyName_x", "CompanyName_y"], errors="ignore")

        # Add selection reason for transparency
        res["selection_reason"] = ""
        for idx in res.index:
            row = res.loc[idx]
            reasons = []
            
            if query_location:
                reasons.append(f"Location: {query_location}")
            
            reasons.append(f"Semantic: {row.get('semantic_score', 0):.3f}")
            reasons.append(f"Keyword: {row.get('keyword_score', 0):.3f}")
            
            res.at[idx, "selection_reason"] = " | ".join(reasons)
        
        # Apply DUAL threshold: require both good semantic AND combined scores
        # This prevents keyword matching from boosting irrelevant results
        # For R&D/facility queries, skip threshold filtering since we'll filter by actual facility data
        if has_rd_keyword or has_test_keyword:
            # No threshold filtering for facility queries - we'll filter by actual facilities
            # This ensures we don't miss companies whose R&D info is only in facility data
            print(f"  Skipping semantic threshold for R&D/facility query (will filter by actual facilities)")
        else:
            semantic_threshold = 0.3  # Require reasonable semantic match
            combined_threshold = 0.25   # Combined score threshold
            # Filter by BOTH thresholds for non-facility queries
            res = res[
                (res["semantic_score"] >= semantic_threshold) & 
                (res["similarity_score"] >= combined_threshold)
            ]
        # Don't limit to top_k yet if we're going to apply facility filter
        if not (has_rd_keyword or has_test_keyword):
            res = res.nlargest(top_k, "similarity_score")
        
        # POST-FILTER: If query explicitly mentions R&D/Test facilities, filter to only companies with those facilities
        
        if has_rd_keyword or has_test_keyword:
            # Load facility data to filter
            try:
                # Collect company IDs from all applicable facility types
                rd_company_ids = None
                test_company_ids = None
                
                if has_rd_keyword:
                    rd_fac_path = self.views_dir / "RDFacilityDetails.csv"
                    if rd_fac_path.exists():
                        rd_fac = pd.read_csv(rd_fac_path, dtype=str)
                        
                        # Content-aware filtering: match query keywords to R&D categories
                        # Extract meaningful keywords from query (exclude common words)
                        query_keywords = set()
                        stop_words = {'companies', 'company', 'doing', 'having', 'with', 'for', 'in', 'at', 'the', 'a', 'an',
                                     'r&d', 'research', 'development', 'facility', 'facilities', 'and', 'both'}
                        for word in query_content.lower().split():
                            word = word.strip('.,?!;:')
                            if word and word not in stop_words and len(word) > 2:
                                query_keywords.add(word)
                        
                        # Filter R&D facilities by matching keywords to RDCategoryName or RDSubCategoryName
                        if query_keywords:
                            # Create a mask for facilities that match the query keywords
                            facility_mask = pd.Series(False, index=rd_fac.index)
                            for keyword in query_keywords:
                                facility_mask |= rd_fac['RDCategoryName'].str.contains(keyword, case=False, na=False)
                                facility_mask |= rd_fac['RDSubCategoryName'].str.contains(keyword, case=False, na=False)
                            
                            rd_fac_filtered = rd_fac[facility_mask]
                            
                            if not rd_fac_filtered.empty:
                                rd_company_ids = set(rd_fac_filtered['CompanyMaster_FK_ID'].unique())
                                print(f"  R&D filter: matched '{', '.join(query_keywords)}' in R&D categories")
                            else:
                                # Fallback to all R&D facilities if no keyword match
                                rd_company_ids = set(rd_fac['CompanyMaster_FK_ID'].unique())
                                print(f"  R&D filter: no specific match, using all R&D facilities")
                        else:
                            # No keywords extracted, use all R&D facilities
                            rd_company_ids = set(rd_fac['CompanyMaster_FK_ID'].unique())
                            print(f"  R&D filter: using all R&D facilities")
                
                if has_test_keyword:
                    test_fac_path = self.views_dir / "TestFacilityDetails.csv"
                    if test_fac_path.exists():
                        test_fac = pd.read_csv(test_fac_path, dtype=str)
                        
                        # Content-aware filtering: match query keywords to facility categories
                        # Extract meaningful keywords from query (exclude common words)
                        query_keywords = set()
                        stop_words = {'companies', 'company', 'having', 'with', 'for', 'in', 'at', 'the', 'a', 'an', 
                                     'testing', 'test', 'facility', 'facilities', 'r&d', 'research', 'development'}
                        for word in query_content.lower().split():
                            word = word.strip('.,?!;:')
                            if word and word not in stop_words and len(word) > 2:
                                query_keywords.add(word)
                        
                        # Filter test facilities by matching keywords to CategoryName or SubCategoryName
                        if query_keywords:
                            # Create a mask for facilities that match the query keywords
                            facility_mask = pd.Series(False, index=test_fac.index)
                            for keyword in query_keywords:
                                facility_mask |= test_fac['CategoryName'].str.contains(keyword, case=False, na=False)
                                facility_mask |= test_fac['SubCategoryName'].str.contains(keyword, case=False, na=False)
                                facility_mask |= test_fac['TestDetails'].str.contains(keyword, case=False, na=False)
                            
                            test_fac_filtered = test_fac[facility_mask]
                            
                            if not test_fac_filtered.empty:
                                test_company_ids = set(test_fac_filtered['CompanyMaster_FK_ID'].unique())
                                print(f"  Test filter: matched '{', '.join(query_keywords)}' in test categories")
                            else:
                                # Fallback to all test facilities if no keyword match
                                test_company_ids = set(test_fac['CompanyMaster_FK_ID'].unique())
                                print(f"  Test filter: no specific match, using all test facilities")
                        else:
                            # No keywords extracted, use all test facilities
                            test_company_ids = set(test_fac['CompanyMaster_FK_ID'].unique())
                            print(f"  Test filter: using all test facilities")
                
                # Combine filters based on what was requested
                initial_count = len(res)
                
                if rd_company_ids is not None and test_company_ids is not None:
                    # BOTH R&D and Test mentioned - check if query wants AND or OR
                    # Look for explicit "and"/"both" vs "or"
                    query_lower_check = query_content.lower()
                    if 'and' in query_lower_check or 'both' in query_lower_check:
                        # AND logic: companies must have BOTH R&D and Test facilities
                        combined_ids = rd_company_ids.intersection(test_company_ids)
                        print(f"  Combined filter (AND): Companies with BOTH R&D and Test facilities")
                    else:
                        # OR logic (default): companies with EITHER R&D or Test facilities
                        combined_ids = rd_company_ids.union(test_company_ids)
                        print(f"  Combined filter (OR): Companies with R&D OR Test facilities")
                    
                    res = res[res['Id'].astype(str).isin(combined_ids)]
                    filtered_count = len(res)
                    print(f"  Facility filter applied: {initial_count} → {filtered_count} companies")
                    
                elif rd_company_ids is not None:
                    # Only R&D filter
                    res = res[res['Id'].astype(str).isin(rd_company_ids)]
                    filtered_count = len(res)
                    print(f"  R&D filter applied: {initial_count} → {filtered_count} companies")
                    
                elif test_company_ids is not None:
                    # Only Test filter
                    res = res[res['Id'].astype(str).isin(test_company_ids)]
                    filtered_count = len(res)
                    print(f"  Test filter applied: {initial_count} → {filtered_count} companies")
                
                # For facility queries, return ALL matching companies (don't limit to top_k)
                if len(res) > 0:
                    print(f"  Returning all {len(res)} companies with specified facilities (not limited to top_k={top_k})")
            except Exception as e:
                print(f"  Warning: Could not apply facility filter: {e}")
            
            # For facility queries, return ALL results sorted by score (don't limit to top_k)
            # This ensures users get all companies with the specified facilities
            res = res.sort_values("similarity_score", ascending=False)

        return res

    def _get_keyword_scores(self, query: str, doc_index: pd.DataFrame) -> Dict[str, float]:
        """Get BM25 keyword scores - cached version for full corpus."""
        qn = query.lower().strip()
        qn = re.sub(r"[^\w\s\-&/]", " ", qn)
        qn = re.sub(r"\s+", " ", qn).strip()
        
        if not hasattr(self, '_bm25') or self._bm25 is None:
            if HAVE_BM25:
                corpus_texts = doc_index["search_text"].tolist()
                corpus_tokens = []
                for text in corpus_texts:
                    tn = text.lower().strip()
                    tn = re.sub(r"[^\w\s\-&/]", " ", tn)
                    tn = re.sub(r"\s+", " ", tn).strip()
                    corpus_tokens.append(tn.split())
                
                self._bm25 = BM25Okapi(corpus_tokens)
                self._bm25_company_ids = doc_index["CompanyId"].tolist()
            else:
                return {}
        
        query_tokens = qn.split()
        scores = self._bm25.get_scores(query_tokens)
        
        return {
            self._bm25_company_ids[i]: float(scores[i]) 
            for i in range(len(scores))
        }
    
    def _get_keyword_scores_filtered(self, query: str, doc_index: pd.DataFrame) -> Dict[str, float]:
        """Get BM25 keyword scores - always rebuild for filtered corpus."""
        if not HAVE_BM25:
            return {}
        
        qn = query.lower().strip()
        qn = re.sub(r"[^\w\s\-&/]", " ", qn)
        qn = re.sub(r"\s+", " ", qn).strip()
        
        # Always rebuild BM25 on the filtered corpus
        corpus_texts = doc_index["search_text"].tolist()
        corpus_tokens = []
        for text in corpus_texts:
            tn = text.lower().strip()
            tn = re.sub(r"[^\w\s\-&/]", " ", tn)
            tn = re.sub(r"\s+", " ", tn).strip()
            corpus_tokens.append(tn.split())
        
        bm25_filtered = BM25Okapi(corpus_tokens)
        company_ids = doc_index["CompanyId"].tolist()
        
        query_tokens = qn.split()
        scores = bm25_filtered.get_scores(query_tokens)
        
        return {
            company_ids[i]: float(scores[i]) 
            for i in range(len(scores))
        }

    def _filter_results_by_query(self, results: pd.DataFrame, query: str) -> pd.DataFrame:
        """
        Filter results to only include companies that match the query intent.
        For company-specific queries (e.g., "Contact of ABC Corp"), return only matching companies.
        """
        if results.empty:
            return results
        
        query_lower = query.lower()
        
        # Check if this is a company-specific query
        is_company_specific = any(keyword in query_lower for keyword in [
            ' of ', ' for ', 'details of', 'address of', 'contact of', 'pan of',
            'cin of', 'gst of', 'email of', 'phone of', 'website of'
        ])
        
        if not is_company_specific:
            # Not a company-specific query - return all results
            return results
        
        # Extract company name from query
        # Try to find text after "of" or "for"
        company_name_match = None
        for pattern in [r'\bof\s+(.+?)(?:\s*$|\s*\?)', r'\bfor\s+(.+?)(?:\s*$|\s*\?)']:
            match = re.search(pattern, query_lower, re.IGNORECASE)
            if match:
                company_name_match = match.group(1).strip()
                break
        
        if not company_name_match:
            # Couldn't extract company name - return all results
            return results
        
        # Clean up the extracted company name
        company_name_match = re.sub(r'\s+', ' ', company_name_match).strip()
        
        # Filter results to only include companies that match
        if 'CompanyName' in results.columns:
            # Tokenize the query company name
            query_tokens = set(company_name_match.lower().split())
            
            # Score each result by how many tokens match
            def match_score(company_name):
                if pd.isna(company_name):
                    return 0
                company_tokens = set(str(company_name).lower().split())
                # Count matching tokens
                matches = len(query_tokens.intersection(company_tokens))
                # Bonus for exact match
                if company_name_match in str(company_name).lower():
                    matches += 10
                return matches
            
            results['_match_score'] = results['CompanyName'].apply(match_score)
            
            # Filter to only companies with at least 2 matching tokens (or exact match)
            min_score = min(2, len(query_tokens))
            filtered = results[results['_match_score'] >= min_score].copy()
            
            if not filtered.empty:
                # Sort by match score (descending) and similarity score if available
                sort_cols = ['_match_score']
                if 'similarity_score' in filtered.columns:
                    sort_cols.append('similarity_score')
                
                filtered = filtered.sort_values(
                    sort_cols, 
                    ascending=[False] * len(sort_cols)
                )
                filtered = filtered.drop('_match_score', axis=1)
                
                print(f"[DEBUG] Filtered from {len(results)} to {len(filtered)} companies matching '{company_name_match}'")
                return filtered.head(5)  # Return top 5 matching companies
            else:
                # No good matches - return top result only
                print(f"[DEBUG] No strong matches for '{company_name_match}', returning top result")
                return results.head(1)
        
        return results

    def natural_language_query(self, question: str, top_k: int = 20) -> Dict[str, Any]:
        """End-to-end NLQ."""
        start_time = datetime.now()
        
        intent = self._analyze_intent(question)
        print(f"\n[DEBUG] Query: '{question}'")
        print(f"[DEBUG] Detected intent: {intent}")
        
        if intent.get("intent") == "company_attribute":
            method = "exact_lookup"
            company_name = intent.get("params", {}).get("company_name", "")
            print(f"[DEBUG] Looking up company: '{company_name}'")
            results = self._lookup_company_by_name(company_name)
            if results.empty:
                print(f"[DEBUG] Exact lookup failed, falling back to semantic search")
                method = "semantic_search_fallback"
                results = self.semantic_search_companies(question, top_k=top_k)
            else:
                print(f"[DEBUG] Found {len(results)} company match(es) via exact lookup")
        elif intent.get("intent") == "filter_list":
            method = "csv_filter"
            results = self._apply_csv_filter(intent, top_k)
        else:
            method = "semantic_search"
            results = self.semantic_search_companies(question, top_k=top_k)
            # Apply post-filtering for company-specific queries
            results = self._filter_results_by_query(results, question)
        
        if self.llm and not results.empty:
            answer = self._generate_answer_llm(question, results, intent)
            answer_method = "llm"
        else:
            answer = self._generate_answer_simple(question, results, intent)
            answer_method = "template"
        
        end_time = datetime.now()
        elapsed = (end_time - start_time).total_seconds()
        
        self._log_query(
            question=question,
            intent=intent,
            method=method,
            answer_method=answer_method,
            results_count=len(results),
            elapsed_time=elapsed,
            top_results=results if not results.empty else pd.DataFrame()
        )
        
        return {"intent": intent, "results": results, "answer": answer, "count": len(results)}
    
    # ==================== OTHER METHODS (unchanged) ====================
    
    def _lookup_company_by_name(self, company_name: str) -> pd.DataFrame:
        """
        Lookup company by name or CompanyRef number.
        Supports: company name, CompanyRef, partial matches
        """
        df = self._load_company_detail()
        
        if df.empty or not company_name:
            return pd.DataFrame()
        
        # Try CompanyRef lookup first (if it looks like a ref number)
        if "CompanyRef" in df.columns and (company_name.isdigit() or company_name.startswith("CB")):
            ref_match = df[df["CompanyRef"].str.lower() == company_name.lower()]
            if not ref_match.empty:
                return ref_match
        
        # Try exact company name match
        if "CompanyName" in df.columns:
            exact_match = df[df["CompanyName"].str.lower() == company_name.lower()]
            if not exact_match.empty:
                return exact_match
            
            # Try partial match
            contains_match = df[df["CompanyName"].str.contains(company_name, case=False, na=False, regex=False)]
            if not contains_match.empty:
                starts_with = contains_match[contains_match["CompanyName"].str.lower().str.startswith(company_name.lower())]
                if not starts_with.empty:
                    return starts_with.head(1)
                return contains_match.head(1)
        
        return pd.DataFrame()
    
    def _apply_csv_filter(self, intent: Dict[str, Any], limit: int = 100) -> pd.DataFrame:
        """Apply direct CSV filtering."""
        df = self._load_company_detail()
        if df.empty:
            return df
        
        params = intent.get("params", {})
        filter_type = params.get("filter_type", "")
        
        if filter_type == "government":
            mask = pd.Series(False, index=df.index)
            if "CompanySubCategory" in df.columns:
                is_govt = df["CompanySubCategory"].str.contains("government company", case=False, na=False, regex=False)
                not_non_govt = ~df["CompanySubCategory"].str.contains("non-government", case=False, na=False, regex=False)
                mask |= (is_govt & not_non_govt)
            if "OrgType" in df.columns:
                mask |= df["OrgType"].str.contains("government|public sector|psu", case=False, na=False, regex=True)
            filtered = df[mask]
            location = params.get("value", "").strip()
            if location and not filtered.empty:
                location_mask = pd.Series(False, index=filtered.index)
                if "State" in filtered.columns:
                    location_mask |= filtered["State"].str.contains(location, case=False, na=False, regex=False)
                if "City" in filtered.columns:
                    location_mask |= filtered["City"].str.contains(location, case=False, na=False, regex=False)
                filtered = filtered[location_mask]
            return filtered.head(limit) if not filtered.empty else pd.DataFrame()
            
        elif filter_type == "defence":
            mask = (
                df["IndustryDomain"].str.contains("defence|defense|military|aerospace", case=False, na=False, regex=True) |
                df["IndustrySubdomain"].str.contains("defence|defense|military|aerospace", case=False, na=False, regex=True)
            )
            return df[mask].head(limit)
            
        elif filter_type == "location":
            location = params.get("value", "").strip()
            if location:
                mask = pd.Series(False, index=df.index)
                for col in ["City", "State", "Address"]:
                    if col in df.columns:
                        mask |= df[col].str.contains(location, case=False, na=False, regex=False)
                return df[mask].head(limit) if mask.any() else df.head(limit)
        
        return df.head(limit)

    def export_results_zip(self, nlq_response: Dict[str, Any], out_zip: str) -> str:
        """Export to ZIP."""
        results: pd.DataFrame = nlq_response.get("results", pd.DataFrame())
        answer  = str(nlq_response.get("answer", "") or "")
        intent  = nlq_response.get("intent", {})

        with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("answer.md", f"# Answer\n\n{answer}\n")
            z.writestr("meta.json", json.dumps({"intent": intent, "count": len(results)}, ensure_ascii=False, indent=2))
            if not results.empty:
                buf = io.StringIO()
                results.to_csv(buf, index=False)
                z.writestr("results.csv", buf.getvalue())
        return out_zip

    # ==================== INTERNALS ====================

    def _ensure_embedder(self):
        if self._embedder is None:
            if not TRANSFORMERS_AVAILABLE:
                raise RuntimeError("sentence-transformers not installed.")
            print(f"Loading embedder: {self._embedder_name} ...")
            self._embedder = SentenceTransformer(self._embedder_name)
            print(" Embedder ready.")

    def _collect_view_files(self) -> Dict[str, Any]:
        vd = self.views_dir
        files = {
            "company": vd / "CompanyDetail.csv",
            "cert":    vd / "CertificationDetail.csv",
            "prod":    vd / "Products.csv",
            # New detail views
            "rd_facility": vd / "RDFacilityDetails.csv",
            "test_facility": vd / "TestFacilityDetails.csv",
            "product_details": vd / "ProductDetails.csv",
            "turnover": vd / "TurnOverDetails.csv",
        }
        present = [str(p) for p in files.values() if p.exists()]
        return {"files": files, "files_present": present}

    def _hash_views(self, present_paths: List[str]) -> str:
        h = hashlib.sha1()
        for p in sorted(present_paths):
            h.update(p.encode("utf-8"))
            try:
                h.update(Path(p).read_bytes())
            except Exception:
                st = Path(p).stat()
                h.update(f"{st.st_mtime_ns}-{st.st_size}".encode("utf-8"))
        return h.hexdigest()[:16]

    def _load_company_detail(self, nrows: Optional[int] = None) -> pd.DataFrame:
        p_enriched = self.views_dir / "CompanyDetailEnriched.csv"
        if p_enriched.exists():
            c = pd.read_csv(p_enriched, dtype=str, nrows=nrows).fillna("")
            print(f"[DEBUG] Loaded from CompanyDetailEnriched.csv: {len(c)} rows")
        else:
            p = self.views_dir / "CompanyDetail.csv"
            if p.exists():
                c = pd.read_csv(p, dtype=str, nrows=nrows).fillna("")
                print(f"[DEBUG] Loaded from CompanyDetail.csv: {len(c)} rows")
            else:
                p2 = self.views_dir / "dbo.CompanyMaster.csv"
                if p2.exists():
                    c = pd.read_csv(p2, dtype=str, nrows=nrows).fillna("")
                    print(f"[DEBUG] Loaded from dbo.CompanyMaster.csv: {len(c)} rows")
                else:
                    c = pd.DataFrame()
                    print(f"[DEBUG] No company data files found in {self.views_dir}")
                if not c.empty and "Id" not in c.columns and "CompanyID" in c.columns:
                    c = c.rename(columns={"CompanyID": "Id"})
        return c

    def _agg_join(self, df: pd.DataFrame, key: str, cols: List[str], sep="; ") -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame(columns=[key] + cols)
        return (
            df.groupby(key, dropna=False)[cols]
              .agg(lambda x: sep.join(sorted({str(v).strip() for v in x if str(v).strip()})))
              .reset_index()
        )

    def _build_company_corpus(self, meta: Dict[str, Any]) -> pd.DataFrame:
        """Build corpus with location-aware processing."""
        C = self._load_company_detail()
        if C.empty:
            raise RuntimeError("CompanyDetail.csv not found")

        if "Id" not in C.columns:
            if "CompanyID" in C.columns:
                C = C.rename(columns={"CompanyID": "Id"})
            else:
                raise RuntimeError("No Id column found")

        files = meta["files"]
        fk = "CompanyMaster_FK_ID"

        def rd_csv(p: Path, nrows: Optional[int] = None) -> pd.DataFrame:
            return pd.read_csv(p, dtype=str, nrows=nrows).fillna("") if p.exists() else pd.DataFrame()

        Cert = rd_csv(files["cert"])
        Prod = rd_csv(files["prod"])
        RDFac = rd_csv(files["rd_facility"])
        TestFac = rd_csv(files["test_facility"])

        for df in (Cert, Prod, RDFac, TestFac):
            if not df.empty and fk not in df.columns:
                if "CompanyID" in df.columns:
                    df.rename(columns={"CompanyID": fk}, inplace=True)
                elif "Company_FK_Id" in df.columns:
                    df.rename(columns={"Company_FK_Id": fk}, inplace=True)

        cert_cols = [c for c in ["CertificationType", "Number", "Year", "Cert_Type"] if c in Cert.columns]
        prod_cols = [c for c in ["ProductName","Category","Description"] if c in Prod.columns]
        rd_fac_cols = [c for c in ["RDCategoryName","RDSubCategoryName"] if c in RDFac.columns]
        test_fac_cols = [c for c in ["CategoryName","SubCategoryName","TestDetails"] if c in TestFac.columns]

        cert_agg = self._agg_join(Cert, fk, cert_cols) if cert_cols else pd.DataFrame(columns=[fk])
        prod_agg = self._agg_join(Prod, fk, prod_cols) if prod_cols else pd.DataFrame(columns=[fk])
        rd_fac_agg = self._agg_join(RDFac, fk, rd_fac_cols) if rd_fac_cols else pd.DataFrame(columns=[fk])
        test_fac_agg = self._agg_join(TestFac, fk, test_fac_cols) if test_fac_cols else pd.DataFrame(columns=[fk])

        view = C.copy()
        if not cert_agg.empty:
            view = view.merge(cert_agg.rename(columns={fk: "Id"}), on="Id", how="left")
        if not prod_agg.empty:
            view = view.merge(prod_agg.rename(columns={fk: "Id"}), on="Id", how="left")
        if not rd_fac_agg.empty:
            view = view.merge(rd_fac_agg.rename(columns={fk: "Id"}), on="Id", how="left")
        if not test_fac_agg.empty:
            view = view.merge(test_fac_agg.rename(columns={fk: "Id"}), on="Id", how="left")

        def pick(col): 
            """Pick column and convert to string, replacing NaN with empty string"""
            if col in view.columns:
                return view[col].fillna("").astype(str)
            else:
                return pd.Series("", index=view.index)
        
        name      = pick("CompanyName")
        city      = pick("City")
        state     = pick("State")
        addr      = pick("Address")
        domain    = pick("IndustryDomain") if "IndustryDomain" in view.columns else pick("Industry")
        subdomain = pick("IndustrySubdomain") if "IndustrySubdomain" in view.columns else pd.Series("", index=view.index)
        comp_subcat = pick("CompanySubCategory")
        orgtype   = pick("OrgType")
        
        # Helper function to check if data is valid (not empty, not "nan")
        def has_valid_data(x):
            """Check if string has meaningful data (not empty, not 'nan')"""
            if not x or pd.isna(x):
                return False
            x_clean = str(x).strip().lower()
            # Check for various representations of empty/null
            return x_clean and x_clean not in ['nan', 'none', 'null', '']
        
        # Build text fields - only add prefixes when data exists
        cert_data = (pick("CertificationType") + " " + pick("Cert_Type") + " " + pick("Number") + " " + pick("Year")).str.strip()
        cert_txt = cert_data.apply(lambda x: f"; {x}" if has_valid_data(x) else "")
        
        prod_data = (pick("ProductName") + " " + pick("Category") + " " + pick("Description")).str.strip()
        prod_txt = prod_data.apply(lambda x: f"; {x}" if has_valid_data(x) else "")
        
        rd_fac_data = (pick("RDCategoryName") + " " + pick("RDSubCategoryName")).str.strip()
        rd_fac_txt = rd_fac_data.apply(lambda x: f"; R&D Facility {x}" if has_valid_data(x) else "")
        
        test_fac_data = (pick("CategoryName") + " " + pick("SubCategoryName") + " " + pick("TestDetails")).str.strip()
        test_fac_txt = test_fac_data.apply(lambda x: f"; Test Facility {x}" if has_valid_data(x) else "")

        # Remove location tokens from search text
        location_combined = (city + " " + state + " " + addr).fillna("")
        location_removed = location_combined.apply(lambda x: _remove_location(x))
        
        view["search_text"] = (
            (name + " ").str.repeat(3) +
            (domain + " " + subdomain + " ").str.repeat(2) +
            (comp_subcat + " " + orgtype + " ").str.repeat(2) +
            location_removed + " " +
            cert_txt + " " + 
            (rd_fac_txt + " ").str.repeat(2) +  # Boost R&D facility weight
            (test_fac_txt + " ").str.repeat(2) +  # Boost test facility weight
            (prod_txt + " ").str.repeat(3)  # Boost product weight to match company name
        ).fillna("").str.replace(r"\s+", " ", regex=True).str.strip()

        return view[["Id", "CompanyName", "search_text"]].rename(columns={"Id": "CompanyId"}).fillna("")

    def _load_index(self) -> Tuple[Optional["np.ndarray"], Optional[pd.DataFrame]]:
        emb_path = self.index_dir / "embeddings.npy"
        idx_path = self.index_dir / "doc_index.csv"
        if not (emb_path.exists() and idx_path.exists()):
            return None, None
        E = np.load(emb_path).astype("float32") if np is not None else None
        D = pd.read_csv(idx_path, dtype=str).fillna("")
        return E, D

    def _keyword_search(self, query: str) -> pd.DataFrame:
        """Fallback keyword search with facility filtering support."""
        print(f"[DEBUG] _keyword_search called with query: '{query}'")
        
        c = self._load_company_detail()
        print(f"[DEBUG] Loaded {len(c)} companies")
        if c.empty:
            print("[DEBUG] Company data is empty!")
            return c
        
        # Check for facility keywords
        query_lower = query.lower()
        print(f"[DEBUG] query_lower: '{query_lower}'")
        rd_keywords = ['r&d', 'r & d', 'research and development', 'research & development', 'r&d facility', 'r&d facilities']
        test_keywords = [
            'test facility', 'test facilities', 'testing facility', 'testing facilities',
            'test lab', 'test labs', 'testing lab', 'testing labs',
            'having test', 'with test', 'test capabilit'
        ]
        has_rd_keyword = any(keyword in query_lower for keyword in rd_keywords)
        has_test_keyword = any(keyword in query_lower for keyword in test_keywords)
        
        # If facility query detected, filter by actual facility data instead of keyword matching
        if has_rd_keyword or has_test_keyword:
            print(f"  Keyword search: Facility query detected (R&D={has_rd_keyword}, Test={has_test_keyword})")
            
            rd_company_ids = None
            test_company_ids = None
            
            # Extract content keywords (excluding facility-related words)
            stop_words = {'companies', 'company', 'list', 'show', 'find', 'having', 'with', 'for', 'in', 'at', 'the', 'a', 'an',
                         'r&d', 'research', 'development', 'testing', 'test', 'facility', 'facilities', 'and', 'both', 'or'}
            query_keywords = set()
            for word in query_lower.split():
                word = word.strip('.,?!;:')
                if word and word not in stop_words and len(word) > 2:
                    query_keywords.add(word)
            
            if has_rd_keyword:
                rd_fac_path = self.views_dir / "RDFacilityDetails.csv"
                if rd_fac_path.exists():
                    rd_fac = pd.read_csv(rd_fac_path, dtype=str)
                    if query_keywords:
                        facility_mask = pd.Series(False, index=rd_fac.index)
                        for keyword in query_keywords:
                            facility_mask |= rd_fac['RDCategoryName'].str.contains(keyword, case=False, na=False)
                            facility_mask |= rd_fac['RDSubCategoryName'].str.contains(keyword, case=False, na=False)
                        rd_fac_filtered = rd_fac[facility_mask] if facility_mask.any() else rd_fac
                    else:
                        rd_fac_filtered = rd_fac
                    rd_company_ids = set(rd_fac_filtered['CompanyMaster_FK_ID'].unique())
                    print(f"  R&D filter: {len(rd_company_ids)} companies")
            
            if has_test_keyword:
                test_fac_path = self.views_dir / "TestFacilityDetails.csv"
                if test_fac_path.exists():
                    test_fac = pd.read_csv(test_fac_path, dtype=str)
                    if query_keywords:
                        facility_mask = pd.Series(False, index=test_fac.index)
                        for keyword in query_keywords:
                            facility_mask |= test_fac['CategoryName'].str.contains(keyword, case=False, na=False)
                            facility_mask |= test_fac['SubCategoryName'].str.contains(keyword, case=False, na=False)
                            facility_mask |= test_fac['TestDetails'].str.contains(keyword, case=False, na=False)
                        test_fac_filtered = test_fac[facility_mask] if facility_mask.any() else test_fac
                    else:
                        test_fac_filtered = test_fac
                    test_company_ids = set(test_fac_filtered['CompanyMaster_FK_ID'].unique())
                    print(f"  Test filter: {len(test_company_ids)} companies")
            
            # Combine filters
            if rd_company_ids is not None and test_company_ids is not None:
                if 'and' in query_lower or 'both' in query_lower:
                    combined_ids = rd_company_ids.intersection(test_company_ids)
                    print(f"  Combined (AND): {len(combined_ids)} companies")
                else:
                    combined_ids = rd_company_ids.union(test_company_ids)
                    print(f"  Combined (OR): {len(combined_ids)} companies")
                return c[c['Id'].astype(str).isin(combined_ids)]
            elif rd_company_ids is not None:
                return c[c['Id'].astype(str).isin(rd_company_ids)]
            elif test_company_ids is not None:
                return c[c['Id'].astype(str).isin(test_company_ids)]
        
        # Default keyword search (non-facility queries)
        tokens = [t for t in re.split(r"[^a-z0-9]+", query.lower()) if t]
        mask = pd.Series(False, index=c.index)
        for col in c.columns:
            s = c[col].astype(str)
            for t in tokens:
                mask |= s.str.contains(t, case=False, na=False, regex=False)
        return c[mask]

    def _analyze_intent(self, q: str) -> Dict[str, Any]:
        """Analyze query intent."""
        if INTENT_HANDLER_AVAILABLE:
            try:
                handler = IntentHandler("intents_reference.json")
                return handler.analyze_query(q)
            except Exception as e:
                print(f"  IntentHandler failed: {e}, using legacy")
        
        # Legacy fallback
        ql = q.lower()
        
        # Company attribute queries
        # Order matters: more specific patterns first
        attr_patterns = [
            (r"(?:contact\s+)?(?:address|location)\s+(?:of|for)\s+(.+)", "address"),  # "contact address" or "address"
            (r"(?:contact|phone|email|details?)\s+(?:of|for)\s+(.+)", "contact"),
            (r"(?:pan|cin|gstin?|registration)\s+(?:of|for)\s+(.+)", "registration"),
            (r"(?:industry\s+type|industry|domain|sector)\s+(?:of|for)\s+(.+)", "industry"),
            (r"(?:products?|services?)\s+(?:of|for|made\s+by|manufactured\s+by)\s+(.+)", "products"),
            (r"(?:turnover|revenue|sales)\s+(?:of|for)\s+(.+)", "turnover"),
        ]
        
        for pattern, intent_type in attr_patterns:
            m = re.search(pattern, ql)
            if m:
                company = m.group(1).strip(" ?.," )
                return {"intent": "company_attribute", "params": {"company_name": company, "attribute": intent_type}}
        
        # Filter queries
        if re.search(r"\b(government|govt)\b.*\bcompan", ql):
            return {"intent": "filter_list", "params": {"filter_type": "government", "field": "subcategory"}}
        if re.search(r"\b(list|show|find|get)\b.*(defence|defense)", ql):
            return {"intent": "filter_list", "params": {"filter_type": "defence", "field": "domain"}}
        
        # Location-only queries (no domain/product keywords) -> use filter_list
        # Location + domain/product queries -> use semantic search for better relevance
        location_match = re.search(r"\b(?:in|from|at|based\s+in)\s+([a-zA-Z\s]+?)(?:\s|$)", ql)
        if location_match:
            location = location_match.group(1).strip()
            if location.lower() not in ["india", "the", "a", "an"]:
                # Check if query also contains domain/product keywords
                has_domain_keywords = bool(re.search(
                    r"\b(making|manufacturing|producing|companies?|firms?|manufacturers?|" +
                    r"drone|uav|uas|aerospace|defence|defense|electronics|software|" +
                    r"pharma|chemical|textile|automotive|food|beverage)\b", ql
                ))
                
                if has_domain_keywords:
                    # Route to semantic search which handles location filtering properly
                    return {"intent": "generic", "params": {}}
                else:
                    # Pure location query - use CSV filter
                    return {"intent": "filter_list", "params": {"filter_type": "location", "field": "location", "value": location}}
        
        return {"intent": "generic", "params": {}}

    def _generate_answer_simple(self, question: str, results: pd.DataFrame, intent: Dict[str, Any]) -> str:
        """Generate simple text answer."""
        if results is None or results.empty:
            return "I couldn't find matching companies."
        
        # Company attribute queries
        if intent.get("intent") == "company_attribute":
            company_name = intent.get("params", {}).get("company_name", "")
            attribute = intent.get("params", {}).get("attribute", "")
            
            if company_name and not results.empty:
                company_col = "CompanyName" if "CompanyName" in results.columns else "Name"
                if company_col in results.columns:
                    mask = results[company_col].str.contains(company_name, case=False, na=False, regex=False)
                    if mask.any():
                        company_row = results[mask].iloc[0]
                        
                        attr_map = {
                            "registration": ["Pan", "CINNumber", "GSTNumber", "CompanyRefNo"],
                            "contact": ["Phone", "EmailId", "POC_Email", "Website"],
                            "industry": ["IndustryDomainName", "IndustrySubDomainName", "CompanyIndustrialClassification"],
                            "address": ["Address", "CityName", "State", "District", "Pincode", "CountryName"],
                            "products": ["CoreExpertiseName", "OtherCompanyCoreExpertise"],
                            "turnover": ["CompanyScale", "OtherScale"],  # Turnover data if available
                        }
                        
                        cols_to_show = attr_map.get(attribute, [])
                        found_data = {}
                        
                        for col in cols_to_show:
                            if col in company_row.index and pd.notna(company_row[col]) and str(company_row[col]).strip():
                                found_data[col] = str(company_row[col])
                        
                        if found_data:
                            company_display_name = company_row.get(company_col, company_name)
                            lines = [f"**{company_display_name}**\n"]
                            for col, val in found_data.items():
                                lines.append(f"- **{col}**: {val}")
                            return "\n".join(lines)
                        else:
                            # No data found for requested attribute
                            return f"No {attribute} information found for {company_row.get(company_col, company_name)}."
                    else:
                        # Company not found in results
                        return f"Company '{company_name}' not found."
        
        # For list queries, show count and top results
        count = len(results)
        if count == 0:
            return "No matching companies found."
        
        lines = [f"Found {count} matching companies:\n"]
        for idx, row in results.head(10).iterrows():
            name = row.get('CompanyName', 'N/A')
            state = row.get('State', 'N/A')
            domain = row.get('IndustryDomainName', row.get('IndustryDomain', 'N/A'))
            city = row.get('CityName', row.get('City', ''))
            location = f"{city}, {state}" if city and city != 'N/A' else state
            lines.append(f"- **{name}** | Location: {location} | Domain: {domain}")
        
        return "\n".join(lines)

    def _generate_answer_llm(self, question: str, results: pd.DataFrame, intent: Dict[str, Any]) -> str:
        """Generate LLM answer."""
        if not self.llm or results.empty:
            return self._generate_answer_simple(question, results, intent)
        
        full_answer = self._generate_answer_simple(question, results, intent)
        
        top_5 = results.head(5)
        summary_data = []
        for _, row in top_5.iterrows():
            company = row.get("CompanyName", "Unknown")
            state = row.get("State", "")
            domain = row.get("IndustryDomainName", row.get("IndustryDomain", ""))
            summary_data.append(f"{company} ({state}, {domain})")
        
        context = " | ".join(summary_data)
        
        prompt = f"""Question: {question}
Found {len(results)} companies. Top: {context}

Write 2-line summary (max 150 chars). Be direct.
Summary:"""
        
        try:
            response = self.llm(prompt, max_tokens=100, temperature=0.3, stop=["\n\n"])
            summary = response.get("choices", [{}])[0].get("text", "").strip()
            summary_lines = [line.strip() for line in summary.split("\n") if line.strip()][:2]
            brief_summary = "\n".join(summary_lines)
            return f"{brief_summary}\n\n{full_answer}"
        except Exception as e:
            print(f"  LLM failed: {e}")
            return full_answer
    
    def _log_query(self, question: str, intent: Dict[str, Any], method: str, 
                   answer_method: str, results_count: int, elapsed_time: float,
                   top_results: pd.DataFrame) -> None:
        """Log query to JSONL."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "question": question,
            "intent": intent.get("intent", "unknown"),
            "intent_params": intent.get("params", {}),
            "search_method": method,
            "answer_method": answer_method,
            "results_count": results_count,
            "elapsed_time_seconds": round(elapsed_time, 2),
            "top_results": []
        }
        
        if not top_results.empty:
            cols_to_log = ["CompanyName", "IndustryDomainName", "CityName", "State"]
            
            for idx, (_, row) in enumerate(top_results.head(10).iterrows(), 1):
                result_entry = {"rank": idx}
                for col in cols_to_log:
                    if col in row.index:
                        val = str(row[col])[:200] if pd.notna(row[col]) else ""
                        result_entry[col] = val
                    # Fallback to old column names if new ones don't exist
                    elif col == "IndustryDomainName" and "IndustryDomain" in row.index:
                        val = str(row["IndustryDomain"])[:200] if pd.notna(row["IndustryDomain"]) else ""
                        result_entry[col] = val
                    elif col == "CityName" and "City" in row.index:
                        val = str(row["City"])[:200] if pd.notna(row["City"]) else ""
                        result_entry[col] = val
                
                if "selection_reason" in row.index:
                    result_entry["selection_reason"] = str(row["selection_reason"])
                
                log_entry["top_results"].append(result_entry)
        
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        except Exception as e:
            print(f"  Warning: Could not write to log: {e}")


# ============================================================================
# CLI
# ============================================================================

def _cli():
    ap = argparse.ArgumentParser(description="Enhanced Query Engine with Location-Aware Matching")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_idx = sub.add_parser("index", help="Build semantic index")
    p_idx.add_argument("--views", default="views", help="Views directory")
    p_idx.add_argument("--model", default="models/all-MiniLM-L6-v2", help="Model path")
    p_idx.add_argument("--force", action="store_true", help="Force rebuild")

    p_q = sub.add_parser("query", help="Query the index")
    p_q.add_argument("--views", default="views", help="Views directory")
    p_q.add_argument("--ask", required=True, help="Natural language query")
    p_q.add_argument("--model", default="models/all-MiniLM-L6-v2", help="Model path")
    p_q.add_argument("--llm", default="", help="Optional LLM path")
    p_q.add_argument("--top-k", type=int, default=20, help="Top K results")
    p_q.add_argument("--zip-out", default="", help="Output ZIP file")

    args = ap.parse_args()

    if args.cmd == "index":
        eng = EnhancedQueryEngine(views_dir=args.views, model_name=args.model)
        eng.build_semantic_index(force=args.force)
    elif args.cmd == "query":
        llm_path = args.llm if args.llm else None
        eng = EnhancedQueryEngine(views_dir=args.views, model_name=args.model, llm_model_path=llm_path)
        resp = eng.natural_language_query(args.ask, top_k=args.top_k)
        
        print("\n=== ANSWER ===")
        print(resp["answer"])
        print()
        
        if isinstance(resp["results"], pd.DataFrame) and not resp["results"].empty:
            cols = [c for c in ["CompanyName","City","State","IndustryDomain","similarity_score"] 
                    if c in resp["results"].columns]
            print(resp["results"][cols].to_string(index=False))
        else:
            print("No results.")
        
        if args.zip_out:
            out_path = Path(args.zip_out).resolve()
            eng.export_results_zip(resp, str(out_path))
            print(f"\n✓ Wrote ZIP: {out_path}")

if __name__ == "__main__":
    _cli()

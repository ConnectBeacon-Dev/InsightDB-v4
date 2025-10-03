#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
enhanced_query_engine.py
- Build semantic embeddings from ALL CSV views first, then search.
- Views expected in <views_dir>:
    CompanyDetail.csv      (Id, CompanyName, City, State, Address, IndustryDomain, ...)
    Certification.csv      (CompanyMaster_FK_ID, CertificationType, Number, Year, ...)
    Facilities.csv         (CompanyMaster_FK_ID, FacilityType[R&D/TEST/MFG], Category, SubCategory, FacilityName, Description, Equipment, Capability, Range, ...)
    Products.csv           (CompanyMaster_FK_ID, ProductName, Category, Description, ...)

Artifacts:
    <views_dir>/.sem_index/
        embeddings.npy     (float32, row-normalized)
        doc_index.csv      (CompanyId, CompanyName, search_text)
        meta.json          (model, dims, content hash, source files)

CLI:
    python enhanced_query_engine.py index  --views views
    python enhanced_query_engine.py query  --views views --ask "electrical domain companies in Pune" [--top-k 20] [--zip-out results.zip]
"""

from __future__ import annotations

import os, re, json, argparse, hashlib, io, zipfile, logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

import pandas as pd

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
    np = None  # we will guard where needed


# --------------------------- Core Engine ---------------------------

class EnhancedQueryEngine:
    def __init__(
        self,
        inputs_dir: str = "inputs",
        views_dir: str = "views",
        model_name: str = "all-MiniLM-L6-v2",    # light, good default
        llm_model_path: Optional[str] = None,     # optional llama.cpp, not required here
        log_file: str = "query_log.jsonl"        # query logging file
    ):
        self.inputs_dir = Path(inputs_dir)
        self.views_dir  = Path(views_dir)
        self.index_dir  = self.views_dir / ".sem_index"
        self.index_dir.mkdir(parents=True, exist_ok=True)
        
        self.log_file = Path(log_file)

        self._embedder_name = model_name
        self._embedder: Optional["SentenceTransformer"] = None  # type: ignore

        # (Optional) local LLM can be wired later if you want synthesized answers.
        self.llm = None
        if llm_model_path:
            try:
                from llama_cpp import Llama  # lazy import
                self.llm = Llama(model_path=llm_model_path, n_ctx=4096, n_threads=max(1, os.cpu_count() or 4))
                print("✅ LLM loaded for optional answer synthesis.")
            except Exception as e:
                print(f"⚠️  Could not load LLM: {e}")

    # -------------------- Public: Build & Query --------------------

    def build_semantic_index(self, force: bool = False) -> None:
        """Build + persist embeddings over ALL views. Rebuilds only if CSV content hash changes."""
        if not TRANSFORMERS_AVAILABLE or np is None:
            print("⚠️  sentence-transformers / numpy not available. Install with:")
            print("    pip install sentence-transformers numpy")
            return

        meta_info = self._collect_view_files()
        content_hash = self._hash_views(meta_info["files_present"])
        meta_path = self.index_dir / "meta.json"
        emb_path  = self.index_dir / "embeddings.npy"
        idx_path  = self.index_dir / "doc_index.csv"

        if meta_path.exists() and emb_path.exists() and idx_path.exists() and not force:
            prev = json.loads(meta_path.read_text(encoding="utf-8"))
            if prev.get("content_hash") == content_hash:
                print("✅ Semantic index already up-to-date.")
                return

        print("🔧 Building semantic index from views...")
        doc_index = self._build_company_corpus(meta_info)  # DataFrame with CompanyId, CompanyName, search_text
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
        print(f"✅ Index built: {emb.shape[0]} companies × {emb.shape[1]} dims")

    def semantic_search_companies(self, query: str, top_k: int = 20) -> pd.DataFrame:
        """Search via the prebuilt semantic index with industry-aware weighted scoring."""
        if not TRANSFORMERS_AVAILABLE or np is None:
            print("⚠️  Semantic search unavailable; falling back to keyword contains search.")
            return self._keyword_search(query)

        # Ensure index ready
        self.build_semantic_index(force=False)

        E, doc_index = self._load_index()
        if E is None or doc_index is None or E.shape[0] == 0:
            print("⚠️  Index missing/empty; fallback to keyword.")
            return self._keyword_search(query)

        self._ensure_embedder()
        qv = self._embedder.encode([query], show_progress_bar=False, convert_to_numpy=True)[0].astype("float32")
        qv = qv / (np.linalg.norm(qv) + 1e-8)

        sims = E @ qv  # cosine since rows are normalized
        
        # Get more candidates for reranking (top_k * 3 to allow filtering)
        k_initial = max(50, int(top_k) * 3)
        idx = np.argsort(sims)[::-1][:k_initial]
        scores = sims[idx]

        top = doc_index.iloc[idx].copy()
        top["base_similarity"] = scores

        # Join for display columns from CompanyDetail
        comp = self._load_company_detail()
        # Ensure CompanyId is string for proper merge
        top["CompanyId"] = top["CompanyId"].astype(str)
        comp["Id"] = comp["Id"].astype(str)
        res = top.merge(comp, left_on="CompanyId", right_on="Id", how="left")
        
        # If CompanyName_x and CompanyName_y exist (duplicate columns), prioritize detail
        if "CompanyName_y" in res.columns:
            res["CompanyName"] = res["CompanyName_y"].fillna(res.get("CompanyName_x", ""))
            res = res.drop(columns=["CompanyName_x", "CompanyName_y"], errors="ignore")

        # Apply industry-aware weighted scoring
        res = self._apply_weighted_scoring(query, res)
        
        # Filter by threshold and take top_k
        threshold = 0.3  # Minimum weighted score
        res = res[res["weighted_score"] >= threshold]
        res = res.nlargest(top_k, "weighted_score")
        
        # Keep both scores for transparency
        res["similarity_score"] = res["weighted_score"]

        return res

    def natural_language_query(self, question: str, top_k: int = 20) -> Dict[str, Any]:
        """End-to-end NLQ (simple intent parse + semantic search + optional LLM answer)."""
        start_time = datetime.now()
        
        intent = self._analyze_intent(question)
        
        # For company attribute queries, do exact name lookup first
        if intent.get("intent") == "company_attribute":
            method = "exact_lookup"
            results = self._lookup_company_by_name(intent.get("params", {}).get("company_name", ""))
            # If no exact match found, fallback to semantic search
            if results.empty:
                method = "semantic_search_fallback"
                results = self.semantic_search_companies(question, top_k=top_k)
        # For filter queries, apply CSV filters instead of semantic search
        elif intent.get("intent") == "filter_list":
            method = "csv_filter"
            results = self._apply_csv_filter(intent, top_k)
        else:
            method = "semantic_search"
            results = self.semantic_search_companies(question, top_k=top_k)
        
        if self.llm and not results.empty:
            answer = self._generate_answer_llm(question, results, intent)
            answer_method = "llm"
        else:
            answer = self._generate_answer_simple(question, results, intent)
            answer_method = "template"
        
        end_time = datetime.now()
        elapsed = (end_time - start_time).total_seconds()
        
        # Log the query
        self._log_query(
            question=question,
            intent=intent,
            method=method,
            answer_method=answer_method,
            results_count=len(results),
            elapsed_time=elapsed,
            top_results=results.head(10) if not results.empty else pd.DataFrame()
        )
        
        return {"intent": intent, "results": results, "answer": answer, "count": len(results)}
    
    def _lookup_company_by_name(self, company_name: str) -> pd.DataFrame:
        """Look up a company by exact or close name match"""
        df = self._load_company_detail()
        if df.empty or not company_name:
            return pd.DataFrame()
        
        # Try exact match first (case-insensitive)
        exact_match = df[df["CompanyName"].str.lower() == company_name.lower()]
        if not exact_match.empty:
            return exact_match
        
        # Try contains match (case-insensitive)
        contains_match = df[df["CompanyName"].str.contains(company_name, case=False, na=False, regex=False)]
        if not contains_match.empty:
            # If multiple matches, prefer the one that starts with the search term
            starts_with = contains_match[contains_match["CompanyName"].str.lower().str.startswith(company_name.lower())]
            if not starts_with.empty:
                return starts_with.head(1)
            return contains_match.head(1)
        
        return pd.DataFrame()
    
    def _apply_csv_filter(self, intent: Dict[str, Any], limit: int = 100) -> pd.DataFrame:
        """Apply direct CSV filtering based on intent parameters"""
        df = self._load_company_detail()
        if df.empty:
            return df
        
        params = intent.get("params", {})
        filter_type = params.get("filter_type", "")
        
        if filter_type == "defence":
            # Filter for defence/defense companies
            mask = (
                df["IndustryDomain"].str.contains("defence|defense|military|aerospace", case=False, na=False, regex=True) |
                df["IndustrySubdomain"].str.contains("defence|defense|military|aerospace", case=False, na=False, regex=True) |
                (df["DefencePlatforms"].str.len() > 0 if "DefencePlatforms" in df.columns else pd.Series(False, index=df.index))
            )
            filtered = df[mask].head(limit)
            
        elif filter_type == "msme":
            # Filter for MSME/Small/Medium companies based on Scale field (NOT company name)
            mask = pd.Series(False, index=df.index)
            
            # Priority 1: Use Scale or CompanyScale field (official scale classification)
            scale_cols = [c for c in ['Scale', 'CompanyScale', 'company_scale'] if c in df.columns]
            for scale_col in scale_cols:
                mask |= df[scale_col].str.contains("micro|small|medium", case=False, na=False, regex=True)
            
            # Priority 2: If no Scale data, use company_size_category
            if not mask.any() and 'company_size_category' in df.columns:
                mask |= df['company_size_category'].str.contains("micro|small|medium", case=False, na=False, regex=True)
            
            # Priority 3: Private/Non-government companies (MSMEs are typically private)
            # But ONLY if they're not marked as "Large" or "Very Large"
            if 'is_private_company' in df.columns:
                private_mask = df['is_private_company'].astype(str).str.lower().isin(['true', '1'])
                # Exclude Large companies
                not_large_mask = pd.Series(True, index=df.index)
                if 'company_size_category' in df.columns:
                    not_large_mask = ~df['company_size_category'].str.contains("large", case=False, na=False, regex=True)
                elif 'CompanyScale' in df.columns:
                    not_large_mask = ~df['CompanyScale'].str.contains("large", case=False, na=False, regex=True)
                
                # Combine: private AND not large
                potential_msme = private_mask & not_large_mask
                mask |= potential_msme
            
            filtered = df[mask].head(limit) if mask.any() else pd.DataFrame()
            
            # Log what we found
            if filtered.empty:
                print("ℹ️  No MSME companies found based on Scale field. Scale data may not be populated.")
                
        elif filter_type == "location":
            # Filter by location (city, state, or address)
            location = params.get("value", "").strip()
            if location:
                mask = pd.Series(False, index=df.index)
                if "City" in df.columns:
                    mask |= df["City"].str.contains(location, case=False, na=False, regex=False)
                if "State" in df.columns:
                    mask |= df["State"].str.contains(location, case=False, na=False, regex=False)
                if "Address" in df.columns:
                    mask |= df["Address"].str.contains(location, case=False, na=False, regex=False)
                filtered = df[mask].head(limit) if mask.any() else df.head(limit)
            else:
                filtered = df.head(limit)
        else:
            # Default: return top companies
            filtered = df.head(limit)
        
        return filtered

    # -------------------- Export (optional ZIP) --------------------

    def export_results_zip(self, nlq_response: Dict[str, Any], out_zip: str) -> str:
        """Writes answer.md, results.csv, meta.json to a ZIP file."""
        results: pd.DataFrame = nlq_response.get("results", pd.DataFrame())
        answer  = str(nlq_response.get("answer", "") or "")
        intent  = nlq_response.get("intent", {})

        out_zip = str(out_zip)
        with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("answer.md", f"# Answer\n\n{answer}\n")
            z.writestr("meta.json", json.dumps({"intent": intent, "count": int(len(results))}, ensure_ascii=False, indent=2))
            if not results.empty:
                buf = io.StringIO(); results.to_csv(buf, index=False)
                z.writestr("results.csv", buf.getvalue())
        return out_zip

    # -------------------- Internals: Views & Index --------------------

    def _ensure_embedder(self):
        if self._embedder is None:
            if not TRANSFORMERS_AVAILABLE:
                raise RuntimeError("sentence-transformers not installed.")
            print(f"Loading embedder: {self._embedder_name} ...")
            self._embedder = SentenceTransformer(self._embedder_name)
            print("✅ Embedder ready.")

    def _collect_view_files(self) -> Dict[str, Any]:
        vd = self.views_dir
        files = {
            "company": vd / "CompanyDetail.csv",
            "cert":    vd / "Certification.csv",
            "fac":     vd / "Facilities.csv",
            "prod":    vd / "Products.csv",
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
        # Prefer CompanyDetailEnriched.csv (has inferred industries + aggregations)
        # Falls back to CompanyDetail.csv, then dbo.CompanyMaster.csv
        # nrows parameter: if specified, only read top N rows (useful for large files)
        p_enriched = self.views_dir / "CompanyDetailEnriched.csv"
        if p_enriched.exists():
            c = pd.read_csv(p_enriched, dtype=str, nrows=nrows).fillna("")
            # CompanyDetailEnriched has many extra columns, but that's fine for our purposes
        else:
            p = self.views_dir / "CompanyDetail.csv"
            if p.exists():
                c = pd.read_csv(p, dtype=str, nrows=nrows).fillna("")
            else:
                p2 = self.views_dir / "dbo.CompanyMaster.csv"
                c = pd.read_csv(p2, dtype=str, nrows=nrows).fillna("") if p2.exists() else pd.DataFrame()
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
        C = self._load_company_detail()
        if C.empty:
            raise RuntimeError("CompanyDetail.csv / dbo.CompanyMaster.csv not found or empty")

        if "Id" not in C.columns:
            if "CompanyID" in C.columns:
                C = C.rename(columns={"CompanyID": "Id"})
            else:
                raise RuntimeError("No Id column found in company view")

        files = meta["files"]
        fk = "CompanyMaster_FK_ID"

        def rd_csv(p: Path, nrows: Optional[int] = None) -> pd.DataFrame:
            return pd.read_csv(p, dtype=str, nrows=nrows).fillna("") if p.exists() else pd.DataFrame()

        # For large datasets, limit rows when building index (can be overridden by caller)
        Cert = rd_csv(files["cert"], nrows=None)
        Fac  = rd_csv(files["fac"], nrows=None)
        Prod = rd_csv(files["prod"], nrows=None)

        # Normalize FK where necessary
        for df in (Cert, Fac, Prod):
            if not df.empty and fk not in df.columns:
                if "CompanyID" in df.columns:
                    df.rename(columns={"CompanyID": fk}, inplace=True)

        # Aggregations
        cert_cols = [c for c in ["CertificationType", "Number", "Year"] if c in Cert.columns]
        fac_cols  = [c for c in ["FacilityType","Category","SubCategory","FacilityName","Description","Equipment","Capability","Range"] if c in Fac.columns]
        prod_cols = [c for c in ["ProductName","Category","Description"] if c in Prod.columns]

        cert_agg = self._agg_join(Cert, fk, cert_cols) if cert_cols else pd.DataFrame(columns=[fk])
        fac_agg  = self._agg_join(Fac,  fk, fac_cols)  if fac_cols  else pd.DataFrame(columns=[fk])
        prod_agg = self._agg_join(Prod, fk, prod_cols) if prod_cols else pd.DataFrame(columns=[fk])

        view = C.copy()
        if not cert_agg.empty:
            view = view.merge(cert_agg.rename(columns={fk: "Id"}), on="Id", how="left")
        if not fac_agg.empty:
            view = view.merge(fac_agg.rename(columns={fk: "Id"}), on="Id", how="left")
        if not prod_agg.empty:
            view = view.merge(prod_agg.rename(columns={fk: "Id"}), on="Id", how="left")

        # Weighted search text
        def pick(col): 
            return view[col].astype(str) if col in view.columns else pd.Series("", index=view.index)
        name      = pick("CompanyName")
        city      = pick("City")
        state     = pick("State")
        addr      = pick("Address")
        domain    = pick("IndustryDomain") if "IndustryDomain" in view.columns else pick("Industry")
        subdomain = pick("IndustrySubdomain") if "IndustrySubdomain" in view.columns else pd.Series("", index=view.index)
        comp_subcat = pick("CompanySubCategory")  # NEW: Include CompanySubCategory
        orgtype   = pick("OrgType")
        cert_txt  = ("; " + pick("CertificationType") + " " + pick("Number") + " " + pick("Year")).fillna("")
        fac_txt   = ("; " + pick("FacilityType") + " " + pick("Category") + " " + pick("SubCategory") + " " +
                     pick("FacilityName") + " " + pick("Description") + " " + pick("Equipment") + " " +
                     pick("Capability") + " " + pick("Range")).fillna("")
        prod_txt  = ("; " + pick("ProductName") + " " + pick("Category") + " " + pick("Description")).fillna("")

        view["search_text"] = (
            (name + " ").str.repeat(3) +  # strong boost
            (domain + " " + subdomain + " ").str.repeat(2) +
            (comp_subcat + " " + orgtype + " ").str.repeat(2) +  # NEW: Boost CompanySubCategory and OrgType
            (city + " " + state + " " + addr + " ") +
            cert_txt + " " + fac_txt + " " + prod_txt
        ).fillna("").str.replace(r"\s+", " ", regex=True).str.strip()

        return view[["Id", "CompanyName", "search_text"]].rename(columns={"Id": "CompanyId"}).fillna("")

    def _load_index(self) -> Tuple[Optional["np.ndarray"], Optional[pd.DataFrame]]:  # type: ignore
        emb_path = self.index_dir / "embeddings.npy"
        idx_path = self.index_dir / "doc_index.csv"
        if not (emb_path.exists() and idx_path.exists()):
            return None, None
        E = np.load(emb_path).astype("float32") if np is not None else None  # type: ignore
        D = pd.read_csv(idx_path, dtype=str).fillna("")
        return E, D

    # -------------------- Fallbacks & Answers --------------------

    def _apply_weighted_scoring(self, query: str, results: pd.DataFrame) -> pd.DataFrame:
        """Apply industry-aware weighted scoring with selection reasons"""
        if results.empty:
            return results
        
        # Extract industry keywords from query
        industry_keywords = {
            'electrical': ['Electrical & Electronics'],
            'electronics': ['Electrical & Electronics'],
            'pharma': ['Pharmaceuticals'],
            'pharmaceutical': ['Pharmaceuticals'],
            'automotive': ['Automotive'],
            'textile': ['Textiles'],
            'steel': ['Steel & Metals'],
            'metal': ['Steel & Metals'],
            'chemical': ['Chemicals'],
            'food': ['Food & Beverages'],
            'software': ['IT & Software'],
            'it': ['IT & Software'],
            'defence': ['Aerospace & Defence'],
            'defense': ['Aerospace & Defence'],
            'aerospace': ['Aerospace & Defence'],
            'plastic': ['Plastics'],
            'machinery': ['Machinery & Equipment'],
            'construction': ['Construction & Engineering'],
        }
        
        query_lower = query.lower()
        query_industries = set()
        for keyword, industries in industry_keywords.items():
            if keyword in query_lower:
                query_industries.update(industries)
        
        # Extract location keywords
        location_patterns = [
            r'\b(pune|mumbai|bangalore|delhi|chennai|hyderabad|kolkata|ahmedabad|bhopal)\b'
        ]
        query_locations = set()
        for pattern in location_patterns:
            matches = re.findall(pattern, query_lower)
            query_locations.update(matches)
        
        # Calculate weighted scores
        results['industry_match'] = False
        results['location_match'] = False
        results['selection_reason'] = ''
        
        for idx in results.index:
            row = results.loc[idx]
            base_score = row.get('base_similarity', 0.5)
            
            reasons = []
            bonuses = []
            
            # Industry matching (strong signal)
            if 'IndustryDomain' in row.index and query_industries:
                domain = str(row['IndustryDomain']).lower()
                for industry in query_industries:
                    if industry.lower() in domain:
                        results.at[idx, 'industry_match'] = True
                        bonuses.append(0.3)  # Strong boost for industry match
                        reasons.append(f"Industry match: {row['IndustryDomain']}")
                        break
            
            # Location matching
            if query_locations:
                location_found = False
                for loc in query_locations:
                    if (('City' in row.index and loc in str(row['City']).lower()) or
                        ('State' in row.index and loc in str(row['State']).lower()) or
                        ('Address' in row.index and loc in str(row['Address']).lower())):
                        results.at[idx, 'location_match'] = True
                        bonuses.append(0.15)  # Moderate boost for location
                        reasons.append(f"Location match: {loc}")
                        location_found = True
                        break
            
            # Base similarity reason
            if base_score > 0.4:
                reasons.append(f"Base similarity: {base_score:.3f}")
            
            # Calculate final weighted score
            total_bonus = sum(bonuses)
            weighted = base_score + total_bonus
            weighted = min(weighted, 1.0)  # Cap at 1.0
            
            results.at[idx, 'weighted_score'] = weighted
            results.at[idx, 'selection_reason'] = ' | '.join(reasons) if reasons else f"Similarity: {base_score:.3f}"
        
        return results

    def _keyword_search(self, query: str) -> pd.DataFrame:
        c = self._load_company_detail()
        if c.empty:
            return c
        tokens = [t for t in re.split(r"[^a-z0-9]+", query.lower()) if t]
        mask = pd.Series(False, index=c.index)
        for col in c.columns:
            s = c[col].astype(str)
            for t in tokens:
                mask |= s.str.contains(t, case=False, na=False, regex=False)
        return c[mask]

    def _analyze_intent(self, q: str) -> Dict[str, Any]:
        ql = q.lower()
        
        # FIRST: Check for attribute queries (company-specific) - highest priority
        # These should be detected before industry/location checks
        attr_patterns = [
            (r"(?:contact|phone|email|details?)\s+(?:of|for)\s+(.+)", "contact"),
            (r"(?:pan|cin|gstin?|registration)\s+(?:of|for)\s+(.+)", "registration"),
            (r"(?:industry\s+type|industry|domain|sector)\s+(?:of|for)\s+(.+)", "industry"),
            (r"(?:address|location)\s+(?:of|for)\s+(.+)", "address"),
            (r"(?:city|state)\s+(?:of|for)\s+(.+)", "location"),
            (r"(?:products?|services?)\s+(?:of|for)\s+(.+)", "products"),
            (r"(?:certifications?)\s+(?:of|for)\s+(.+)", "certifications"),
            (r"(?:facilities)\s+(?:of|for)\s+(.+)", "facilities"),
            (r"(?:turnover|revenue)\s+(?:of|for)\s+(.+)", "turnover"),
            (r"what\s+(?:is|are)\s+the\s+(.+?)\s+(?:of|for)\s+(.+)", "attribute"),
        ]
        
        for pattern, intent_type in attr_patterns:
            m = re.search(pattern, ql)
            if m:
                if intent_type == "attribute":
                    attr = m.group(1).strip()
                    company = m.group(2).strip(" ?.," )
                else:
                    company = m.group(1).strip(" ?.," )
                    attr = intent_type
                return {"intent": "company_attribute", "params": {"company_name": company, "attribute": attr}}
        
        # SECOND: Check for industry keywords to determine if this is a combined query
        industry_keywords = [
            'electrical', 'electronics', 'pharma', 'pharmaceutical', 'automotive',
            'textile', 'steel', 'metal', 'chemical', 'food', 'software', 'it',
            'defence', 'defense', 'aerospace', 'plastic', 'machinery', 'construction'
        ]
        has_industry = any(keyword in ql for keyword in industry_keywords)
        
        # Check for location keywords
        location_match = re.search(r"\b(?:in|from|at|based\s+in)\s+([a-zA-Z\s]+?)(?:\s|$)", ql)
        has_location = location_match is not None
        
        # If both industry and location are mentioned, use semantic search (not CSV filter)
        if has_industry and has_location:
            return {"intent": "generic", "params": {"industry_filter": True, "location_filter": True}}
        
        # Check for government company queries
        if re.search(r"\b(government|govt)\b.*\bcompan", ql) or re.search(r"\bcompan.*\b(government|govt)\b", ql):
            return {"intent": "filter_list", "params": {"filter_type": "government", "field": "subcategory"}}
        
        # Check for list/filter queries (only if no industry keyword)
        if re.search(r"\b(list|show|find|get)\b.*(defence|defense)", ql) and not has_industry:
            return {"intent": "filter_list", "params": {"filter_type": "defence", "field": "domain"}}
        
        if re.search(r"\b(msme|micro|small|medium)\b", ql):
            return {"intent": "filter_list", "params": {"filter_type": "msme", "field": "scale"}}
        
        # Location-only queries (no industry keyword)
        if has_location and not has_industry:
            location = location_match.group(1).strip()
            # Common words to exclude
            if location.lower() not in ["india", "the", "a", "an", "all", "any"]:
                return {"intent": "filter_list", "params": {"filter_type": "location", "field": "location", "value": location}}
        
        # Generic queries
        return {"intent": "generic", "params": {}}

    def _generate_answer_simple(self, question: str, results: pd.DataFrame, intent: Dict[str, Any]) -> str:
        if results is None or results.empty:
            return "I couldn't find matching companies."
        
        # Handle company attribute queries specifically
        if intent.get("intent") == "company_attribute":
            company_name = intent.get("params", {}).get("company_name", "")
            attribute = intent.get("params", {}).get("attribute", "")
            
            # Try to find exact or close match by company name
            if company_name and not results.empty:
                # Case-insensitive match
                company_col = "CompanyName" if "CompanyName" in results.columns else "Name"
                if company_col in results.columns:
                    mask = results[company_col].str.contains(company_name, case=False, na=False, regex=False)
                    if mask.any():
                        company_row = results[mask].iloc[0]
                        
                        # Map attribute to column names (case-sensitive - match actual CSV columns)
                        attr_map = {
                            "registration": ["Pan", "CIN", "CINNumber", "GSTIN", "GST", "RegistrationDate"],
                            "contact": ["Phone", "Email", "Website", "POCEmail"],
                            "industry": ["IndustryDomain", "Industry", "Domain", "IndustrySubdomain"],
                            "address": ["Address", "City", "State", "District", "Pincode"],
                            "location": ["City", "State", "Address", "District", "Pincode"],
                            "products": ["ProductName", "Products"],
                            "certifications": ["CertificationType", "Certifications"],
                            "facilities": ["FacilityType", "FacilityName"],
                            "turnover": ["TurnOver", "Revenue"],
                        }
                        
                        # Find matching columns
                        cols_to_show = attr_map.get(attribute, [])
                        found_data = {}
                        
                        for col in cols_to_show:
                            if col in company_row.index and pd.notna(company_row[col]) and str(company_row[col]).strip():
                                found_data[col] = str(company_row[col])
                        
                        if found_data:
                            lines = [f"For {company_row.get(company_col, company_name)}:"]
                            for col, val in found_data.items():
                                lines.append(f"  {col}: {val}")
                            return "\n".join(lines)
                        else:
                            # No data found for the requested attribute, show what we have
                            lines = [f"For {company_row.get(company_col, company_name)}:"]
                            lines.append(f"  ⚠️  {attribute.title()} information not available in database")
                            # Show other available fields
                            other_fields = {}
                            for col in ["City", "State", "Address", "OrgType", "Scale", "CoreExpertise"]:
                                if col in company_row.index and pd.notna(company_row[col]) and str(company_row[col]).strip():
                                    other_fields[col] = str(company_row[col])
                            if other_fields:
                                lines.append("  Available information:")
                                for col, val in other_fields.items():
                                    lines.append(f"    {col}: {val}")
                            return "\n".join(lines)
        
        # Default: show top matches
        cols = [c for c in ["CompanyRefNo","CompanyName","City","State","IndustryDomain"] if c in results.columns]
        if not cols:
            cols = [c for c in results.columns if c not in ["search_text", "similarity_score"]][:4]
        preview = results.head(10)[cols]
        lines = ["Top matches:"]
        for _, row in preview.iterrows():
            parts = [f"{c}: {row[c]}" for c in cols if pd.notna(row.get(c)) and str(row[c]).strip()]
            lines.append(" - " + " | ".join(parts))
        return "\n".join(lines)

    def _generate_answer_llm(self, question: str, results: pd.DataFrame, intent: Dict[str, Any]) -> str:
        # Simple prompt grounded on top rows
        ctx_cols = [c for c in ["CompanyName","City","State","IndustryDomain","Address"] if c in results.columns]
        ctx = "\n".join(["; ".join(f"{c}: {row[c]}" for c in ctx_cols if pd.notna(row.get(c))) for _, row in results.head(12).iterrows()])
        prompt = f"""You are a helpful assistant. Using ONLY the data rows below, answer the user briefly.
User question: {question}

DATA ROWS:
{ctx}

Answer:"""
        try:
            out = self.llm(prompt=prompt, max_tokens=256, temperature=0.2)
            return out["choices"][0]["text"].strip()
        except Exception:
            return self._generate_answer_simple(question, results, intent)
    
    def _log_query(self, question: str, intent: Dict[str, Any], method: str, 
                   answer_method: str, results_count: int, elapsed_time: float,
                   top_results: pd.DataFrame) -> None:
        """Log query details to JSONL file for offline analysis"""
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
        
        # Add top results with reasoning
        if not top_results.empty:
            cols_to_log = ["CompanyName", "IndustryDomain", "IndustryDomain_Source", 
                          "City", "State", "ProductNames_Sample"]
            
            for idx, (_, row) in enumerate(top_results.head(10).iterrows(), 1):
                result_entry = {"rank": idx}
                for col in cols_to_log:
                    if col in row.index:
                        val = str(row[col])[:200] if pd.notna(row[col]) else ""
                        result_entry[col] = val
                
                # Add explanation for why this result was selected
                if method == "csv_filter":
                    filter_type = intent.get("params", {}).get("filter_type", "")
                    if filter_type == "defence":
                        result_entry["selection_reason"] = f"IndustryDomain contains defence/aerospace: {row.get('IndustryDomain', '')}"
                    elif filter_type == "msme":
                        result_entry["selection_reason"] = "Company name or type matches MSME/Micro/Small/Medium keywords"
                    elif filter_type == "location":
                        location = intent.get("params", {}).get("value", "")
                        result_entry["selection_reason"] = f"Location matches: {location}"
                elif method == "semantic_search":
                    similarity = row.get("similarity_score", "N/A")
                    result_entry["selection_reason"] = f"Semantic similarity score: {similarity}"
                
                log_entry["top_results"].append(result_entry)
        
        # Append to log file (JSONL format - one JSON object per line)
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        except Exception as e:
            print(f"⚠️  Warning: Could not write to log file: {e}")


# --------------------------- CLI ---------------------------

def _cli():
    ap = argparse.ArgumentParser(description="Enhanced Query Engine (embeddings-first)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_idx = sub.add_parser("index", help="Build semantic index from views")
    p_idx.add_argument("--views", default="views", help="Path to views directory")
    p_idx.add_argument("--model", default="all-MiniLM-L6-v2", help="Sentence-Transformers model name")
    p_idx.add_argument("--force", action="store_true", help="Force rebuild even if up-to-date")

    p_q = sub.add_parser("query", help="Query the semantic index")
    p_q.add_argument("--views", default="views", help="Path to views directory")
    p_q.add_argument("--ask", required=True, help="Natural language query")
    p_q.add_argument("--model", default="all-MiniLM-L6-v2", help="Sentence-Transformers model name")
    p_q.add_argument("--llm", default="", help="Optional: Path to LLM model file (llama.cpp compatible)")
    p_q.add_argument("--top-k", type=int, default=20, help="Top K results")
    p_q.add_argument("--zip-out", default="", help="Optional: write answer+results to ZIP")

    args = ap.parse_args()

    if args.cmd == "index":
        eng = EnhancedQueryEngine(views_dir=args.views, model_name=args.model)
        eng.build_semantic_index(force=args.force)
    elif args.cmd == "query":
        llm_path = args.llm if args.llm else None
        eng = EnhancedQueryEngine(views_dir=args.views, model_name=args.model, llm_model_path=llm_path)
        resp = eng.natural_language_query(args.ask, top_k=args.top_k)
        # Pretty print summary to console
        print("\n=== ANSWER ===\n" + resp["answer"] + "\n")
        if isinstance(resp["results"], pd.DataFrame) and not resp["results"].empty:
            cols = [c for c in ["CompanyRefNo","CompanyName","City","State","IndustryDomain","similarity_score"] if c in resp["results"].columns]
            print(resp["results"].head(15)[cols].to_string(index=False))
        else:
            print("No rows.")
        if args.zip_out:
            out_path = Path(args.zip_out).resolve()
            eng.export_results_zip(resp, str(out_path))
            print(f"\n📦 Wrote ZIP: {out_path}")

if __name__ == "__main__":
    _cli()

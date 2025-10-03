#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
build_views_pandas.py  —  drop-in

Usage:
  python etl/build_views_pandas.py --inputs ./inputs --views ./views

What it does:
  1) Scans --inputs for likely CSVs and builds normalized views:
       CompanyDetail.csv, Certification.csv, Facilities.csv, Products.csv
     (Facilities merges R&D/Test/Mfg sources into one table with FacilityType)
  2) Applies hard-wired "TableScan" field selection (no Excel required)
  3) Writes merged, company-centric outputs:
       MergedCompanyView.csv, MergedCompanyView.json, MergedCompanyView.jsonl
  4) Writes tablescan_config.json (presets & hints for the query engine)
"""

from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd

# Import classification utilities
from add_classifications import add_company_classifications, write_company_classifications
from entity_classification_helpers import classify_product, classify_facility, classify_certification

# ================== INLINE SCHEMA CONFIG (no Excel) ==================
# Which columns to KEEP for each output view (case-insensitive match).
TABLE_FIELDS: Dict[str, List[str]] = {
    "companydetail": [
        "Id", "CompanyRefNo", "CompanyName", "LegalName",
        "IndustryDomain", "IndustrySubdomain", "CoreExpertise",
        "OrgType", "Scale", "CompanyStatus", "CompanySubCategory", "ListingStatus",
        "Address", "City", "State", "Country", "Pincode",
        "Website", "Email", "Phone",
        "CIN", "GST", "PAN", "DUNS",
        "Lat", "Lng"
    ],
    "companydetailenriched": [
        "Id", "CompanyRefNo", "CompanyName", "LegalName",
        "IndustryDomain", "IndustrySubdomain", "CoreExpertise",
        "OrgType", "Scale", "CompanyStatus", "CompanySubCategory", "ListingStatus",
        "Address", "City", "State", "Country", "Pincode",
        "Website", "Email", "Phone",
        "CIN", "GST", "PAN", "DUNS",
        "Lat", "Lng",
        # Classification fields
        "is_union_government", "is_state_government", "is_government_company",
        "is_private_company", "is_msme", "is_listed_company", "is_active_company",
        "is_defence_company", "company_size_category", "company_type_normalized"
    ],
    "certification": [
        "CompanyMaster_FK_ID",
        "CertificationType", "Number", "Issuer", "Status",
        "Year", "ValidFrom", "ValidTo"
    ],
    "facilities": [
        "CompanyMaster_FK_ID",
        "FacilityType", "Category", "SubCategory", "FacilityName",
        "Description", "Equipment", "Capability", "Range", "Accreditation"
    ],
    "products": [
        "CompanyMaster_FK_ID",
        "ProductId", "ProductName", "Category", "ProductType",
        "Description", "HSCode", "IsConsumable", "DefencePlatform", "TechArea"
    ],
    # If you output "CompanyDetailEnriched.csv", you can add key list here too.
}

# Optional: named filters you want available downstream (e.g., “government”).
FILTER_PRESETS = {
    "government": {
        "table": "CompanyClassifications", "field": "is_government_company",
        "include_values": [True, "true", "True", "1"]
    },
    "union_government": {
        "table": "CompanyClassifications", "field": "is_union_government",
        "include_values": [True, "true", "True", "1"]
    },
    "state_government": {
        "table": "CompanyClassifications", "field": "is_state_government",
        "include_values": [True, "true", "True", "1"]
    },
    "private_company": {
        "table": "CompanyClassifications", "field": "is_private_company",
        "include_values": [True, "true", "True", "1"]
    },
    "msme": {
        "table": "CompanyClassifications", "field": "is_msme",
        "include_values": [True, "true", "True", "1"]
    },
    "defence": {
        "table": "CompanyClassifications", "field": "is_defence_company",
        "include_values": [True, "true", "True", "1"]
    },
    "listed_company": {
        "table": "CompanyClassifications", "field": "is_listed_company",
        "include_values": [True, "true", "True", "1"]
    },
    "active_company": {
        "table": "CompanyClassifications", "field": "is_active_company",
        "include_values": [True, "true", "True", "1"]
    },
}

# Hints your search/routing can use (good match fields, keys).
MATCH_HINTS = {
    "companydetail": {
        "primary_keys": ["Id"],
        "alternate_name_fields": ["CompanyName", "LegalName"],
        "geo_fields": ["City", "State", "Address"]
    },
    "certification": {
        "foreign_keys": ["CompanyMaster_FK_ID"],
        "match_fields": ["CertificationType", "Number", "Issuer"]
    },
    "facilities": {
        "foreign_keys": ["CompanyMaster_FK_ID"],
        "match_fields": ["FacilityType", "Category", "SubCategory", "FacilityName", "Description"]
    },
    "products": {
        "foreign_keys": ["CompanyMaster_FK_ID"],
        "match_fields": ["ProductName", "Category", "Description"]
    },
}
# =====================================================================


# --------------------------- Utilities ---------------------------

def _norm_tbl_name(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower()).strip()

def _apply_field_selection(df: pd.DataFrame, logical_name: str) -> pd.DataFrame:
    """
    Keep only TABLE_FIELDS[logical_name] (case-insensitive), but always retain IDs if present.
    """
    if df is None or df.empty:
        return df
    wanted = TABLE_FIELDS.get(_norm_tbl_name(logical_name))
    if not wanted:
        return df

    existing_lower = {c.lower(): c for c in df.columns}
    keep = set()
    for w in wanted:
        lw = w.lower()
        if lw in existing_lower:
            keep.add(existing_lower[lw])
        else:
            # soft match on normalized tokens (handles underscores/spaces)
            wn = _norm_tbl_name(w)
            for c in df.columns:
                if _norm_tbl_name(c) == wn:
                    keep.add(c)

    # Always keep IDs where present
    for k in ("Id", "CompanyMaster_FK_ID"):
        if k in df.columns:
            keep.add(k)

    if not keep:
        print(f"⚠️  Field selection for '{logical_name}' matched nothing; leaving columns unchanged.")
        return df

    ordered = [c for c in df.columns if c in keep]
    missing = [w for w in wanted if w.lower() not in existing_lower]
    if missing:
        print(f"ℹ️  '{logical_name}': missing requested columns skipped: {missing[:6]}{' ...' if len(missing)>6 else ''}")
    return df[ordered]


def _read_csv(p: Path) -> pd.DataFrame:
    if not p.exists():
        return pd.DataFrame()
    # Try multiple encodings
    for encoding in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
        try:
            return pd.read_csv(p, dtype=str, encoding=encoding).fillna("")
        except (UnicodeDecodeError, Exception):
            continue
    # Last resort: try semicolon separator with different encodings
    for encoding in ['utf-8', 'latin-1', 'cp1252']:
        try:
            return pd.read_csv(p, dtype=str, sep=";", engine="python", encoding=encoding).fillna("")
        except Exception:
            continue
    return pd.DataFrame()


def _find_file(inputs: Path, name_candidates: List[str]) -> Optional[Path]:
    """Return the first file that exists, case-insensitive substring match allowed."""
    # exact matches first
    for nm in name_candidates:
        p = inputs / nm
        if p.exists():
            return p
    # case-insensitive and substring scan over CSVs
    all_csvs = list(inputs.glob("*.csv"))
    lower_index = {f.name.lower(): f for f in all_csvs}
    for nm in name_candidates:
        nm_l = nm.lower()
        if nm_l in lower_index:
            return lower_index[nm_l]
        # substring
        for k, f in lower_index.items():
            if nm_l in k:
                return f
    return None


def _ensure_id(df: pd.DataFrame) -> pd.DataFrame:
    """Make sure Company Id column is named 'Id' on the master."""
    if df.empty:
        return df
    if "Id" in df.columns:
        return df
    for alt in ("CompanyID", "CompanyId", "companyid", "ID"):
        if alt in df.columns:
            return df.rename(columns={alt: "Id"})
    return df


def _ensure_fk(df: pd.DataFrame) -> pd.DataFrame:
    """Make sure foreign key column is named 'CompanyMaster_FK_ID' on child tables."""
    if df.empty:
        return df
    if "CompanyMaster_FK_ID" in df.columns:
        return df
    for alt in ("CompanyID", "CompanyId", "Id", "MasterId", "CompanyMasterId"):
        if alt in df.columns:
            return df.rename(columns={alt: "CompanyMaster_FK_ID"})
    return df


def _select_cols(df: pd.DataFrame, rename_map: Dict[str,str]) -> pd.DataFrame:
    """Rename known variants to canonical names when present."""
    if df.empty:
        return df
    cols = {c: rename_map.get(c, c) for c in df.columns}
    return df.rename(columns=cols)


# --------------------------- Master Table Enrichment ---------------------------

def _enrich_with_master_tables(df: pd.DataFrame, inputs: Path) -> pd.DataFrame:
    """
    Enrich company data by joining with master reference tables to get actual text values
    instead of FK IDs (e.g., IndustryDomain text instead of IndustryDomain_Fk_Id).
    """
    if df.empty:
        return df
    
    # Load master tables
    industry_domain_master = _read_csv(inputs / "dbo.IndustryDomainMaster.csv")
    industry_subdomain_master = _read_csv(inputs / "dbo.IndustrySubdomainMaster.csv")
    org_type_master = _read_csv(inputs / "dbo.OrganisationTypeMaster.csv")
    scale_master = _read_csv(inputs / "dbo.ScaleMaster.csv")
    core_expertise_master = _read_csv(inputs / "dbo.CompanyCoreExpertiseMaster.csv")
    
    # Join IndustryDomain
    if not industry_domain_master.empty and 'IndustryDomain_Fk_Id' in df.columns:
        industry_domain_master = industry_domain_master.rename(columns={'Id': 'IndustryDomain_Fk_Id'})
        if 'IndustryDomainName' in industry_domain_master.columns:
            df = df.merge(
                industry_domain_master[['IndustryDomain_Fk_Id', 'IndustryDomainName']], 
                on='IndustryDomain_Fk_Id', 
                how='left'
            )
            df['IndustryDomain'] = df['IndustryDomainName'].fillna('')
            df = df.drop(columns=['IndustryDomainName'], errors='ignore')
    
    # Join IndustrySubdomain
    if not industry_subdomain_master.empty and 'IndustrySubDomain_Fk_Id' in df.columns:
        industry_subdomain_master = industry_subdomain_master.rename(columns={'Id': 'IndustrySubDomain_Fk_Id'})
        if 'SubDomainName' in industry_subdomain_master.columns:
            df = df.merge(
                industry_subdomain_master[['IndustrySubDomain_Fk_Id', 'SubDomainName']], 
                on='IndustrySubDomain_Fk_Id', 
                how='left'
            )
            df['IndustrySubdomain'] = df['SubDomainName'].fillna('')
            df = df.drop(columns=['SubDomainName'], errors='ignore')
    
    # Join OrgType
    if not org_type_master.empty and 'CompanyType_Fk_Id' in df.columns:
        org_type_master = org_type_master.rename(columns={'Id': 'CompanyType_Fk_Id'})
        if 'OrganisationType' in org_type_master.columns:
            df = df.merge(
                org_type_master[['CompanyType_Fk_Id', 'OrganisationType']], 
                on='CompanyType_Fk_Id', 
                how='left'
            )
            df['OrgType'] = df['OrganisationType'].fillna('')
            df = df.drop(columns=['OrganisationType'], errors='ignore')
    
    # Join Scale
    if not scale_master.empty and 'CompanyScale_Fk_Id' in df.columns:
        scale_master = scale_master.rename(columns={'Id': 'CompanyScale_Fk_Id'})
        if 'ScaleName' in scale_master.columns:
            df = df.merge(
                scale_master[['CompanyScale_Fk_Id', 'ScaleName']], 
                on='CompanyScale_Fk_Id', 
                how='left'
            )
            df['Scale'] = df['ScaleName'].fillna('')
            df = df.drop(columns=['ScaleName'], errors='ignore')
    
    # Join CoreExpertise
    if not core_expertise_master.empty and 'CompanyCoreExpertise_Fk_Id' in df.columns:
        core_expertise_master = core_expertise_master.rename(columns={'Id': 'CompanyCoreExpertise_Fk_Id'})
        if 'CoreExpertise' in core_expertise_master.columns:
            df = df.merge(
                core_expertise_master[['CompanyCoreExpertise_Fk_Id', 'CoreExpertise']], 
                on='CompanyCoreExpertise_Fk_Id', 
                how='left'
            )
            # CoreExpertise column already exists from the merge
        elif 'CoreExpertiseName' in core_expertise_master.columns:
            df = df.merge(
                core_expertise_master[['CompanyCoreExpertise_Fk_Id', 'CoreExpertiseName']], 
                on='CompanyCoreExpertise_Fk_Id', 
                how='left'
            )
            df['CoreExpertise'] = df['CoreExpertiseName'].fillna('')
            df = df.drop(columns=['CoreExpertiseName'], errors='ignore')
    
    return df

# --------------------------- Builders ---------------------------

def build_company_detail(inputs: Path) -> pd.DataFrame:
    p = _find_file(inputs, [
        "CompanyDetail.csv",
        "dbo.CompanyMaster.csv",
        "CompanyMaster.csv",
    ])
    if not p:
        raise SystemExit("❌ Could not find CompanyDetail / CompanyMaster CSV in inputs.")
    df = _read_csv(p)
    df = _ensure_id(df)
    
    # Enrich with master table lookups
    df = _enrich_with_master_tables(df, inputs)
    
    # Light canonicalization
    ren = {
        "Company Name": "CompanyName",
        "Legal Name": "LegalName",
        "Industry": "IndustryDomain",
        "Industry Domain": "IndustryDomain",
        "Industry Subdomain": "IndustrySubdomain",
        "Org Type": "OrgType",
        "PinCode": "Pincode",
    }
    df = _select_cols(df, ren).fillna("")
    return df


def build_certification_view(inputs: Path) -> pd.DataFrame:
    p = _find_file(inputs, [
        "CompanyCertificationDetail.csv",
        "CompanyCertification.csv",
        "Certification.csv",
        "Certifications.csv",
        "Cert.csv",
    ])
    if not p:
        return pd.DataFrame(columns=[
            "CompanyMaster_FK_ID","CertificationType","Number","Issuer","Status","Year","ValidFrom","ValidTo"
        ])
    df = _read_csv(p)
    df = _ensure_fk(df)
    ren = {
        "CertType": "CertificationType",
        "Cert Number": "Number",
        "CertificateNumber": "Number",
        "IssuedBy": "Issuer",
        "Valid From": "ValidFrom",
        "Valid To": "ValidTo",
    }
    df = _select_cols(df, ren).fillna("")
    # keep only useful columns
    keep = ["CompanyMaster_FK_ID","CertificationType","Number","Issuer","Status","Year","ValidFrom","ValidTo"]
    df = df[[c for c in df.columns if c in keep]]
    return df


def _read_fac(inputs: Path, name: str, ftype: str) -> pd.DataFrame:
    p = _find_file(inputs, [name])
    if not p:
        return pd.DataFrame()
    df = _read_csv(p)
    df = _ensure_fk(df)
    df["FacilityType"] = ftype
    ren = {
        "Sub Category": "SubCategory",
        "Facility Name": "FacilityName",
        "Capabilities": "Capability",
        "Equipments": "Equipment",
        "AccreditedBy": "Accreditation",
    }
    df = _select_cols(df, ren).fillna("")
    keep = ["CompanyMaster_FK_ID","FacilityType","Category","SubCategory","FacilityName","Description","Equipment","Capability","Range","Accreditation"]
    return df[[c for c in df.columns if c in keep]]


def build_facilities_view(inputs: Path) -> pd.DataFrame:
    # Union of possible sources, each tagged by FacilityType
    parts = []
    # Unified single file variants
    uni = _find_file(inputs, ["Facilities.csv","CompanyFacilities.csv"])
    if uni:
        dfu = _read_csv(uni)
        dfu = _ensure_fk(dfu)
        if "FacilityType" not in dfu.columns:
            # try to infer from filename, else mark as 'TEST'
            kind = "TEST"
            parts.append(_select_cols(dfu.assign(FacilityType=kind), {}))
        else:
            parts.append(_select_cols(dfu, {}))
    # Separate files
    parts.append(_read_fac(inputs, "CompanyRDFacility.csv", "R&D"))
    parts.append(_read_fac(inputs, "CompanyTestFacility.csv", "TEST"))
    parts.append(_read_fac(inputs, "CompanyManufacturingFacility.csv", "MFG"))

    parts = [p for p in parts if not p.empty]
    if not parts:
        return pd.DataFrame(columns=[
            "CompanyMaster_FK_ID","FacilityType","Category","SubCategory","FacilityName","Description","Equipment","Capability","Range","Accreditation"
        ])
    df = pd.concat(parts, ignore_index=True).fillna("")
    # Standardize columns
    keep = ["CompanyMaster_FK_ID","FacilityType","Category","SubCategory","FacilityName","Description","Equipment","Capability","Range","Accreditation"]
    df = df[[c for c in df.columns if c in keep]]
    return df


def build_products_view(inputs: Path) -> pd.DataFrame:
    p = _find_file(inputs, [
        "CompanyProducts.csv","CompanyProduct.csv","Products.csv","Product.csv","CompanyProductDetail.csv"
    ])
    if not p:
        return pd.DataFrame(columns=[
            "CompanyMaster_FK_ID","ProductId","ProductName","Category","ProductType","Description","HSCode","IsConsumable","DefencePlatform","TechArea"
        ])
    df = _read_csv(p)
    df = _ensure_fk(df)
    # Map actual source columns to canonical names
    ren = {
        "Product ID": "ProductId",
        "Product Name": "ProductName",
        "ProductDesc": "Description",  # dbo.CompanyProducts uses ProductDesc
        "HSNCode": "HSCode",           # dbo.CompanyProducts uses HSNCode
        "HS Code": "HSCode",
        "Tech Area": "TechArea",
        "DefensePlatform": "DefencePlatform",
        "ProductRefNo": "ProductId",   # If ProductId not present
    }
    df = _select_cols(df, ren).fillna("")
    keep = ["CompanyMaster_FK_ID","ProductId","ProductName","Category","ProductType","Description","HSCode","IsConsumable","DefencePlatform","TechArea"]
    df = df[[c for c in df.columns if c in keep]]
    return df


# --------------------------- Merged outputs ---------------------------

def write_merged_company_csv(out_dir: Path, company: pd.DataFrame, cert: pd.DataFrame, fac: pd.DataFrame, prod: pd.DataFrame) -> Path:
    """Write a denormalized company-level CSV with aggregated child text fields."""
    if company.empty:
        raise SystemExit("CompanyDetail is empty; cannot write merged CSV.")
    fk = "CompanyMaster_FK_ID"

    def agg_join(df: pd.DataFrame, key: str, cols: List[str], sep="; ") -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame(columns=[key] + cols)
        return (df.groupby(key, dropna=False)[cols]
                  .agg(lambda x: sep.join(sorted({str(v).strip() for v in x if str(v).strip()})))
                  .reset_index())

    cert_cols = [c for c in ["CertificationType","Number","Year"] if c in cert.columns]
    fac_cols  = [c for c in ["FacilityType","Category","SubCategory","FacilityName","Description","Equipment","Capability","Range"] if c in fac.columns]
    prod_cols = [c for c in ["ProductName","Category","Description"] if c in prod.columns]

    cagg = agg_join(cert, fk, cert_cols) if cert_cols else pd.DataFrame(columns=[fk])
    fagg = agg_join(fac,  fk, fac_cols)  if fac_cols  else pd.DataFrame(columns=[fk])
    pagg = agg_join(prod, fk, prod_cols) if prod_cols else pd.DataFrame(columns=[fk])

    C = company.copy()
    if "Id" not in C.columns:
        raise SystemExit("CompanyDetail must contain an 'Id' column after normalization.")
    if not cagg.empty: C = C.merge(cagg.rename(columns={fk: "Id"}), on="Id", how="left")
    if not fagg.empty: C = C.merge(fagg.rename(columns={fk: "Id"}), on="Id", how="left")
    if not pagg.empty: C = C.merge(pagg.rename(columns={fk: "Id"}), on="Id", how="left")

    # selection (optional; only if you added a companydetailenriched list)
    out_path = out_dir / "MergedCompanyView.csv"
    C.fillna("").to_csv(out_path, index=False)
    return out_path


def write_merged_company_json(out_dir: Path, company: pd.DataFrame, cert: pd.DataFrame, fac: pd.DataFrame, prod: pd.DataFrame) -> None:
    """Write per-company JSON + JSONL with nested arrays (certifications/facilities/products)."""
    if company.empty:
        raise SystemExit("CompanyDetail is empty; cannot write merged JSON.")
    fk = "CompanyMaster_FK_ID"

    # Fast lookups
    cert_by = {}
    if not cert.empty:
        for _, r in cert.iterrows():
            cert_by.setdefault(r.get(fk, ""), []).append({
                "type": r.get("CertificationType",""),
                "number": r.get("Number",""),
                "issuer": r.get("Issuer",""),
                "status": r.get("Status",""),
                "year": r.get("Year",""),
                "valid_from": r.get("ValidFrom",""),
                "valid_to": r.get("ValidTo",""),
            })

    fac_by = {}
    if not fac.empty:
        for _, r in fac.iterrows():
            fac_by.setdefault(r.get(fk, ""), []).append({
                "facility_type": r.get("FacilityType",""),
                "category": r.get("Category",""),
                "subcategory": r.get("SubCategory",""),
                "name": r.get("FacilityName",""),
                "desc": r.get("Description",""),
                "equipment": r.get("Equipment",""),
                "capability": r.get("Capability",""),
                "range": r.get("Range",""),
                "accreditation": r.get("Accreditation",""),
            })

    prod_by = {}
    if not prod.empty:
        for _, r in prod.iterrows():
            prod_by.setdefault(r.get(fk, ""), []).append({
                "product_id": r.get("ProductId",""),
                "name": r.get("ProductName",""),
                "category": r.get("Category",""),
                "type": r.get("ProductType",""),
                "desc": r.get("Description",""),
                "hs_code": r.get("HSCode",""),
                "is_consumable": r.get("IsConsumable",""),
                "defence_platform": r.get("DefencePlatform",""),
                "tech_area": r.get("TechArea",""),
            })

    def norm_key(s: str) -> str:
        return re.sub(r"[^a-z0-9]+","", (s or "").lower()).strip()

    objects = []
    for _, row in company.iterrows():
        cid = row.get("Id","")
        obj = {
            "id": cid,
            "name": row.get("CompanyName",""),
            "legal_name": row.get("LegalName",""),
            "domain": row.get("IndustryDomain",""),
            "subdomain": row.get("IndustrySubdomain",""),
            "core_expertise": row.get("CoreExpertise",""),
            "org_type": row.get("OrgType",""),
            "scale": row.get("Scale",""),
            "address": row.get("Address",""),
            "city": row.get("City",""),
            "state": row.get("State",""),
            "country": row.get("Country",""),
            "pincode": row.get("Pincode",""),
            "lat": row.get("Lat",""),
            "lng": row.get("Lng",""),
            "website": row.get("Website",""),
            "email": row.get("Email",""),
            "phone": row.get("Phone",""),
            "pan": row.get("PAN",""),
            "cin": row.get("CIN",""),
            "gst": row.get("GST",""),
            "duns": row.get("DUNS",""),
            "name_key": norm_key(row.get("CompanyName","")),
            # Classification fields
            "is_government_company": row.get("is_government_company", False),
            "is_union_government": row.get("is_union_government", False),
            "is_state_government": row.get("is_state_government", False),
            "is_private_company": row.get("is_private_company", False),
            "is_msme": row.get("is_msme", False),
            "is_listed_company": row.get("is_listed_company", False),
            "is_active_company": row.get("is_active_company", False),
            "is_defence_company": row.get("is_defence_company", False),
            "company_size_category": row.get("company_size_category", "Unknown"),
            "company_type_normalized": row.get("company_type_normalized", "Unknown"),
            "certifications": cert_by.get(cid, []),
            "facilities": fac_by.get(cid, []),
            "products": prod_by.get(cid, []),
        }
        objects.append(obj)

    (out_dir / "MergedCompanyView.json").write_text(json.dumps(objects, ensure_ascii=False, indent=2), encoding="utf-8")
    with open(out_dir / "MergedCompanyView.jsonl", "w", encoding="utf-8") as w:
        for obj in objects:
            w.write(json.dumps(obj, ensure_ascii=False) + "\n")


# --------------------------- Entrypoint ---------------------------

def main():
    ap = argparse.ArgumentParser(description="Build normalized views + merged outputs (pandas)")
    ap.add_argument("--inputs", default="inputs", help="Folder with raw CSVs")
    ap.add_argument("--views",  default="views",  help="Output folder for views")
    args = ap.parse_args()

    IN = Path(args.inputs)
    OUT = Path(args.views)
    OUT.mkdir(parents=True, exist_ok=True)

    # 1) Build views
    print("• Building CompanyDetail ...")
    df_company = build_company_detail(IN)
    df_company = _apply_field_selection(df_company, "CompanyDetail")
    df_company.to_csv(OUT / "CompanyDetail.csv", index=False)
    print(f"  -> {OUT/'CompanyDetail.csv'} ({len(df_company)} rows)")
    
    # 1b) Add company classifications
    print("• Adding company classifications ...")
    df_company_enriched = df_company.copy()
    df_company_enriched = add_company_classifications(df_company_enriched, str(IN))
    
    # Write enriched version with classifications
    df_company_enriched_selected = _apply_field_selection(df_company_enriched, "CompanyDetailEnriched")
    df_company_enriched_selected.to_csv(OUT / "CompanyDetailEnriched.csv", index=False)
    print(f"  -> {OUT/'CompanyDetailEnriched.csv'} ({len(df_company_enriched_selected)} rows)")
    
    # Write separate classifications file
    write_company_classifications(OUT, df_company_enriched)

    print("• Building Certification ...")
    df_cert = build_certification_view(IN)
    
    # Add certification classifications
    print("  → Classifying certifications...")
    if not df_cert.empty:
        cert_classifications = []
        for _, row in df_cert.iterrows():
            result = classify_certification(row.get('CertificationType', ''), row.get('Number', ''), row.get('Issuer', ''))
            cert_classifications.append(result)
        df_cert['CertCategory'] = [c['category'] for c in cert_classifications]
        df_cert['CertScope'] = [c['scope'] if c['scope'] else '' for c in cert_classifications]
        print(f"  → Classified {len([c for c in cert_classifications if c['category'] != 'General'])} certifications")
    
    df_cert = _apply_field_selection(df_cert, "Certification")
    df_cert.to_csv(OUT / "Certification.csv", index=False)
    print(f"  -> {OUT/'Certification.csv'} ({len(df_cert)} rows)")

    print("• Building Facilities ...")
    df_fac = build_facilities_view(IN)
    
    # Add facility classifications
    print("  → Classifying facilities...")
    if not df_fac.empty:
        fac_classifications = []
        for _, row in df_fac.iterrows():
            result = classify_facility(row.get('FacilityName', ''), row.get('Description', ''), row.get('FacilityType', ''), row.get('Equipment', ''))
            fac_classifications.append(result)
        df_fac['FacilityPrimaryType'] = [c['primary_type'] for c in fac_classifications]
        df_fac['SuggestedAccreditation'] = [c['accreditation_suggested'] if c['accreditation_suggested'] else '' for c in fac_classifications]
        print(f"  → Classified {len([c for c in fac_classifications if c['primary_type'] != 'Other'])} facilities")
    
    df_fac = _apply_field_selection(df_fac, "Facilities")
    df_fac.to_csv(OUT / "Facilities.csv", index=False)
    print(f"  -> {OUT/'Facilities.csv'} ({len(df_fac)} rows)")

    print("• Building Products ...")
    df_prod = build_products_view(IN)
    
    # Add product classifications
    print("  → Classifying products...")
    if not df_prod.empty and 'ProductName' in df_prod.columns:
        classifications = []
        for _, row in df_prod.iterrows():
            result = classify_product(
                row.get('ProductName', ''),
                row.get('Description', ''),
                row.get('HSCode', '')
            )
            classifications.append(result)
        
        df_prod['ProductCategory'] = [c['category'] for c in classifications]
        df_prod['IndustryFromHSN'] = [c['industry'] for c in classifications]
        print(f"  → Classified {len([c for c in classifications if c['category'] != 'Other'])} products into categories")
    
    df_prod = _apply_field_selection(df_prod, "Products")
    df_prod.to_csv(OUT / "Products.csv", index=False)
    print(f"  -> {OUT/'Products.csv'} ({len(df_prod)} rows)")

    # 2) Merged company outputs (CSV + JSON + JSONL) - using enriched company data
    print("• Writing merged company CSV ...")
    merged_csv = write_merged_company_csv(OUT, df_company_enriched, df_cert, df_fac, df_prod)
    print(f"  -> {merged_csv}")

    print("• Writing merged company JSON/JSONL ...")
    write_merged_company_json(OUT, df_company_enriched, df_cert, df_fac, df_prod)
    print(f"  -> {OUT/'MergedCompanyView.json'}")
    print(f"  -> {OUT/'MergedCompanyView.jsonl'}")

    # 3) Emit config for your query engine (optional but handy)
    cfg_path = OUT / "tablescan_config.json"
    cfg_path.write_text(json.dumps({
        "tables": {k: {"must_fields": v} for k, v in TABLE_FIELDS.items()},
        "filter_presets": FILTER_PRESETS,
        "match_hints": MATCH_HINTS,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"• Wrote {cfg_path}")

    print("\n✅ Done. Views written to:", OUT.resolve())

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        sys.exit(130)

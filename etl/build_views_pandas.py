#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
build_views_pandas.py  —  drop-in

Usage:
  python etl/build_views_pandas.py --inputs ./inputs --views ./views

What it does:
  1) Scans --inputs for likely CSVs and builds normalized views:
       CompanyDetail.csv, Certification.csv, Products.csv, and various detail views
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
from entity_classification_helpers import classify_product, classify_facility, classify_certification

# ================== INLINE SCHEMA CONFIG (no Excel) ==================
# Which columns to KEEP for each output view (case-insensitive match).
TABLE_FIELDS: Dict[str, List[str]] = {
    "companydetail": [
        "Id", "CINNumber", "Pan", "GSTNumber", "CompanyRefNo", "CompanyName",
        "POC_Email", "Phone", "EmailId", "Address", "CityName", "Pincode",
        "CountryName", "DisplayCountryName", "District", "State", "Website",
        "CompanyScale", "Organisation_Type", "IndustryDomainName", "IndustrySubDomainName",
        "CoreExpertiseName", "CompanyRegistrationDate", "CompanyStatus",
        "CompanyCategory", "CompanySubCategory", "CompanyClass", "ListingStatus",
        "CompanyROC", "CompanyIndustrialClassification",
        "OtherScale", "OtherCompanyType", "OtherCompanyCoreExpertise",
        "OtherCompIndDomain", "OtherCompIndSubDomain",
        "is_msme", "is_government", "is_private",
        # Aggregated facility and product information
        "HasCertifications", "CertificationCount", "CertificationTypes",
        "HasProducts", "ProductCount", "ProductNames", "ProductCategories",
        "HasRDFacility", "RDFacilityCount", "RDCategories", "RDSubCategories",
        "HasTestFacility", "TestFacilityCount", "TestCategories", "TestSubCategories"
    ],
    "certificationdetail": [
        "CompanyRefNo", "CompanyName",
        "Certification_Type", "Certificate_No",
        "Certificate_StartDate", "Certificate_EndDate",
        "Cert_Type"
    ],
    "products": [
        "CompanyMaster_FK_ID",
        "ProductId", "ProductName", "Category", "ProductType",
        "Description", "HSCode", "IsConsumable", "DefencePlatform", "TechArea"
    ],
    "rdfacilitydetails": [
        "CompanyMaster_FK_ID", "CompanyName", "IDMId", "CompanyRefNo",
        "RDCategoryName", "RDSubCategoryName"
    ],
    "testfacilitydetails": [
        "CompanyMaster_FK_ID", "CompanyName", "CompanyRefNo", "TestDetails",
        "IsNablAccredited", "CategoryName", "SubCategoryName"
    ],
    "productdetails": [
        "CompanyMaster_FK_ID", "CompanyName", "CompanyRefNo", "ProductName",
        "ProductDesc", "NSNNumber", "HSNCode", "FutureExpansion",
        "AnnualProductionCapacity", "ProductCertificateDet", "ProductTypeName",
        "Name_of_Defence_Platform", "PTAName", "SalientFeature", "PARTNo",
        "Remarks", "ItemExported", "OtherDefencePlatform", "OtherTypeProduct", "OtherPTA"
    ],
    "turnoverdetails": [
        "Company_FK_Id", "CompanyName", "Year", "Amount"
    ],
    # If you output "CompanyDetailEnriched.csv", you can add key list here too.
}

# Optional: named filters you want available downstream (e.g., "government").
FILTER_PRESETS = {
    "government": {
        "table": "CompanyDetail", "field": "is_government",
        "include_values": [True, "true", "True", "1"]
    },
    "private_company": {
        "table": "CompanyDetail", "field": "is_private",
        "include_values": [True, "true", "True", "1"]
    },
    "msme": {
        "table": "CompanyDetail", "field": "is_msme",
        "include_values": [True, "true", "True", "1"]
    },
    "defence": {
        "table": "CompanyDetail", "field": "is_defence",
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
    "certificationdetail": {
        "foreign_keys": ["CompanyRefNo"],
        "match_fields": ["Certification_Type", "Certificate_No", "Cert_Type"]
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
        print(f"  Field selection for '{logical_name}' matched nothing; leaving columns unchanged.")
        return df

    ordered = [c for c in df.columns if c in keep]
    missing = [w for w in wanted if w.lower() not in existing_lower]
    if missing:
        print(f"ℹ  '{logical_name}': missing requested columns skipped: {missing[:6]}{' ...' if len(missing)>6 else ''}")
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
    instead of FK IDs. Keeps the resolved names as separate columns.
    """
    if df.empty:
        return df
    
    # Load master tables
    country_master = _read_csv(inputs / "dbo.CountryMaster.csv")
    industry_domain_master = _read_csv(inputs / "dbo.IndustryDomainMaster.csv")
    industry_subdomain_master = _read_csv(inputs / "dbo.IndustrySubdomainMaster.csv")
    org_type_master = _read_csv(inputs / "dbo.OrganisationTypeMaster.csv")
    scale_master = _read_csv(inputs / "dbo.CompanyScaleMaster.csv")
    core_expertise_master = _read_csv(inputs / "dbo.CompanyCoreExpertiseMaster.csv")
    
    # Join Country
    if not country_master.empty and 'Country_Fk_Id' in df.columns:
        country_master_renamed = country_master.rename(columns={'Id': 'Country_Fk_Id'})
        cols_to_merge = ['Country_Fk_Id']
        if 'CountryName' in country_master.columns:
            cols_to_merge.append('CountryName')
        if 'DisplayCountryName' in country_master.columns:
            cols_to_merge.append('DisplayCountryName')
        if len(cols_to_merge) > 1:
            df = df.merge(
                country_master_renamed[cols_to_merge], 
                on='Country_Fk_Id', 
                how='left'
            )
    
    # Join IndustryDomain
    if not industry_domain_master.empty and 'IndustryDomain_Fk_Id' in df.columns:
        industry_domain_master_renamed = industry_domain_master.rename(columns={'Id': 'IndustryDomain_Fk_Id'})
        if 'IndustryDomainName' in industry_domain_master.columns:
            df = df.merge(
                industry_domain_master_renamed[['IndustryDomain_Fk_Id', 'IndustryDomainName']], 
                on='IndustryDomain_Fk_Id', 
                how='left'
            )
    
    # Join IndustrySubdomain
    if not industry_subdomain_master.empty and 'IndustrySubDomain_Fk_Id' in df.columns:
        industry_subdomain_master_renamed = industry_subdomain_master.rename(columns={'Id': 'IndustrySubDomain_Fk_Id'})
        # Try both possible column names
        subdomain_col = None
        if 'IndustrySubDomainName' in industry_subdomain_master.columns:
            subdomain_col = 'IndustrySubDomainName'
        elif 'SubDomainName' in industry_subdomain_master.columns:
            subdomain_col = 'SubDomainName'
            industry_subdomain_master_renamed = industry_subdomain_master_renamed.rename(columns={'SubDomainName': 'IndustrySubDomainName'})
        
        if subdomain_col:
            merge_cols = ['IndustrySubDomain_Fk_Id', 'IndustrySubDomainName'] if subdomain_col == 'SubDomainName' else ['IndustrySubDomain_Fk_Id', subdomain_col]
            df = df.merge(
                industry_subdomain_master_renamed[merge_cols], 
                on='IndustrySubDomain_Fk_Id', 
                how='left'
            )
    
    # Join OrgType
    if not org_type_master.empty and 'CompanyType_Fk_Id' in df.columns:
        org_type_master_renamed = org_type_master.rename(columns={'Id': 'CompanyType_Fk_Id'})
        # Try both possible column names
        if 'Organisation_Type' in org_type_master.columns:
            df = df.merge(
                org_type_master_renamed[['CompanyType_Fk_Id', 'Organisation_Type']], 
                on='CompanyType_Fk_Id', 
                how='left'
            )
        elif 'OrganisationType' in org_type_master.columns:
            org_type_master_renamed = org_type_master_renamed.rename(columns={'OrganisationType': 'Organisation_Type'})
            df = df.merge(
                org_type_master_renamed[['CompanyType_Fk_Id', 'Organisation_Type']], 
                on='CompanyType_Fk_Id', 
                how='left'
            )
    
    # Join Scale
    if not scale_master.empty and 'CompanyScale_Fk_Id' in df.columns:
        scale_master_renamed = scale_master.rename(columns={'Id': 'CompanyScale_Fk_Id'})
        # Try both possible column names
        if 'CompanyScale' in scale_master.columns:
            df = df.merge(
                scale_master_renamed[['CompanyScale_Fk_Id', 'CompanyScale']], 
                on='CompanyScale_Fk_Id', 
                how='left'
            )
        elif 'ScaleName' in scale_master.columns:
            scale_master_renamed = scale_master_renamed.rename(columns={'ScaleName': 'CompanyScale'})
            df = df.merge(
                scale_master_renamed[['CompanyScale_Fk_Id', 'CompanyScale']], 
                on='CompanyScale_Fk_Id', 
                how='left'
            )
    
    # Join CoreExpertise
    if not core_expertise_master.empty and 'CompanyCoreExpertise_Fk_Id' in df.columns:
        core_expertise_master_renamed = core_expertise_master.rename(columns={'Id': 'CompanyCoreExpertise_Fk_Id'})
        if 'CoreExpertiseName' in core_expertise_master.columns:
            df = df.merge(
                core_expertise_master_renamed[['CompanyCoreExpertise_Fk_Id', 'CoreExpertiseName']], 
                on='CompanyCoreExpertise_Fk_Id', 
                how='left'
            )
        elif 'CoreExpertise' in core_expertise_master.columns:
            core_expertise_master_renamed = core_expertise_master_renamed.rename(columns={'CoreExpertise': 'CoreExpertiseName'})
            df = df.merge(
                core_expertise_master_renamed[['CompanyCoreExpertise_Fk_Id', 'CoreExpertiseName']], 
                on='CompanyCoreExpertise_Fk_Id', 
                how='left'
            )
    
    return df

# --------------------------- Builders ---------------------------

def build_company_detail(inputs: Path) -> pd.DataFrame:
    p = _find_file(inputs, [
        "CompanyDetail.csv",
        "dbo.CompanyMaster.csv",
        "CompanyMaster.csv",
    ])
    if not p:
        raise SystemExit(" Could not find CompanyDetail / CompanyMaster CSV in inputs.")
    df = _read_csv(p)
    df = _ensure_id(df)
    
    # Enrich with master table lookups
    df = _enrich_with_master_tables(df, inputs)
    
    # Standardize column names
    ren = {
        "Company Name": "CompanyName",
        "CIN": "CINNumber",
        "GST": "GSTNumber",
        "PAN": "Pan",
        "Email": "EmailId",
        "City": "CityName",
        "PinCode": "Pincode",
        "WebSite": "Website",
        "Web Site": "Website",
        "POCEmail": "POC_Email",
        "POC Email": "POC_Email",
        "PoC_Email": "POC_Email",
    }
    df = _select_cols(df, ren)
    
    # Add classification fields
    df = _add_simple_classifications(df)
    
    df = df.fillna("")
    return df


def _add_simple_classifications(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add simple classification fields: is_msme, is_government, is_private
    """
    if df.empty:
        return df
    
    # is_msme: from Organisation_Type or CompanyScale
    df['is_msme'] = False
    if 'Organisation_Type' in df.columns:
        df['is_msme'] = df['Organisation_Type'].str.contains(
            'micro|small|medium|msme', case=False, na=False, regex=True
        )
    if 'CompanyScale' in df.columns and not df['is_msme'].any():
        df['is_msme'] = df['is_msme'] | df['CompanyScale'].str.contains(
            'micro|small|medium|msme', case=False, na=False, regex=True
        )
    
    # is_government: from Organisation_Type or CompanySubCategory
    df['is_government'] = False
    if 'Organisation_Type' in df.columns:
        df['is_government'] = df['Organisation_Type'].str.contains(
            'public limited|psu|dpsu|government', case=False, na=False, regex=True
        )
    if 'CompanySubCategory' in df.columns:
        df['is_government'] = df['is_government'] | df['CompanySubCategory'].str.contains(
            'union government company|state government company', case=False, na=False, regex=True
        )
    
    # is_private: inverse of is_government
    df['is_private'] = ~df['is_government']
    
    return df


def _enrich_with_aggregated_data(company_df: pd.DataFrame, cert_df: pd.DataFrame, prod_df: pd.DataFrame, 
                                  rd_fac_df: pd.DataFrame, test_fac_df: pd.DataFrame) -> pd.DataFrame:
    """
    Enrich CompanyDetail with aggregated information from certifications, products, and facilities.
    Adds columns like HasCertifications, CertificationTypes, HasProducts, ProductNames, etc.
    """
    if company_df.empty:
        return company_df
    
    # Helper function to aggregate text fields
    def aggregate_text(df, group_key, text_col, sep=", "):
        """Aggregate unique non-empty values from a text column"""
        if df.empty or text_col not in df.columns:
            return pd.DataFrame(columns=[group_key, text_col + '_Agg'])
        
        result = df.groupby(group_key)[text_col].apply(
            lambda x: sep.join(sorted(set(str(v).strip() for v in x if str(v).strip() and str(v).lower() not in ['nan', 'none', ''])))
        ).reset_index()
        result.columns = [group_key, text_col + '_Agg']
        return result
    
    # Certification aggregation
    if not cert_df.empty and 'CompanyRefNo' in cert_df.columns and 'CompanyRefNo' in company_df.columns:
        # Count certifications
        cert_counts = cert_df.groupby('CompanyRefNo').size().reset_index(name='CertificationCount')
        company_df = company_df.merge(cert_counts, on='CompanyRefNo', how='left')
        
        # Aggregate certification types
        if 'Cert_Type' in cert_df.columns:
            cert_types = aggregate_text(cert_df, 'CompanyRefNo', 'Cert_Type')
            company_df = company_df.merge(cert_types.rename(columns={'Cert_Type_Agg': 'CertificationTypes'}), 
                                         on='CompanyRefNo', how='left')
        
        # Add HasCertifications flag
        company_df['HasCertifications'] = company_df['CertificationCount'].fillna(0) > 0
    else:
        company_df['HasCertifications'] = False
        company_df['CertificationCount'] = 0
        company_df['CertificationTypes'] = ''
    
    # Product aggregation
    if not prod_df.empty and 'CompanyMaster_FK_ID' in prod_df.columns and 'Id' in company_df.columns:
        # Count products
        prod_counts = prod_df.groupby('CompanyMaster_FK_ID').size().reset_index(name='ProductCount')
        prod_counts['CompanyMaster_FK_ID'] = prod_counts['CompanyMaster_FK_ID'].astype(str)
        company_df['Id_str'] = company_df['Id'].astype(str)
        company_df = company_df.merge(prod_counts, left_on='Id_str', right_on='CompanyMaster_FK_ID', how='left')
        company_df = company_df.drop(columns=['CompanyMaster_FK_ID', 'Id_str'])
        
        # Aggregate product names
        if 'ProductName' in prod_df.columns:
            prod_names = aggregate_text(prod_df, 'CompanyMaster_FK_ID', 'ProductName')
            prod_names['CompanyMaster_FK_ID'] = prod_names['CompanyMaster_FK_ID'].astype(str)
            company_df['Id_str'] = company_df['Id'].astype(str)
            company_df = company_df.merge(prod_names.rename(columns={'ProductName_Agg': 'ProductNames'}), 
                                         left_on='Id_str', right_on='CompanyMaster_FK_ID', how='left')
            company_df = company_df.drop(columns=['CompanyMaster_FK_ID', 'Id_str'])
        
        # Aggregate product categories
        if 'Category' in prod_df.columns:
            prod_cats = aggregate_text(prod_df, 'CompanyMaster_FK_ID', 'Category')
            prod_cats['CompanyMaster_FK_ID'] = prod_cats['CompanyMaster_FK_ID'].astype(str)
            company_df['Id_str'] = company_df['Id'].astype(str)
            company_df = company_df.merge(prod_cats.rename(columns={'Category_Agg': 'ProductCategories'}), 
                                         left_on='Id_str', right_on='CompanyMaster_FK_ID', how='left')
            company_df = company_df.drop(columns=['CompanyMaster_FK_ID', 'Id_str'])
        
        # Add HasProducts flag
        company_df['HasProducts'] = company_df['ProductCount'].fillna(0) > 0
    else:
        company_df['HasProducts'] = False
        company_df['ProductCount'] = 0
        company_df['ProductNames'] = ''
        company_df['ProductCategories'] = ''
    
    # R&D Facility aggregation
    if not rd_fac_df.empty and 'CompanyMaster_FK_ID' in rd_fac_df.columns and 'Id' in company_df.columns:
        # Count R&D facilities
        rd_counts = rd_fac_df.groupby('CompanyMaster_FK_ID').size().reset_index(name='RDFacilityCount')
        rd_counts['CompanyMaster_FK_ID'] = rd_counts['CompanyMaster_FK_ID'].astype(str)
        company_df['Id_str'] = company_df['Id'].astype(str)
        company_df = company_df.merge(rd_counts, left_on='Id_str', right_on='CompanyMaster_FK_ID', how='left')
        company_df = company_df.drop(columns=['CompanyMaster_FK_ID', 'Id_str'])
        
        # Aggregate R&D categories
        if 'RDCategoryName' in rd_fac_df.columns:
            rd_cats = aggregate_text(rd_fac_df, 'CompanyMaster_FK_ID', 'RDCategoryName')
            rd_cats['CompanyMaster_FK_ID'] = rd_cats['CompanyMaster_FK_ID'].astype(str)
            company_df['Id_str'] = company_df['Id'].astype(str)
            company_df = company_df.merge(rd_cats.rename(columns={'RDCategoryName_Agg': 'RDCategories'}), 
                                         left_on='Id_str', right_on='CompanyMaster_FK_ID', how='left')
            company_df = company_df.drop(columns=['CompanyMaster_FK_ID', 'Id_str'])
        
        # Aggregate R&D subcategories
        if 'RDSubCategoryName' in rd_fac_df.columns:
            rd_subcats = aggregate_text(rd_fac_df, 'CompanyMaster_FK_ID', 'RDSubCategoryName')
            rd_subcats['CompanyMaster_FK_ID'] = rd_subcats['CompanyMaster_FK_ID'].astype(str)
            company_df['Id_str'] = company_df['Id'].astype(str)
            company_df = company_df.merge(rd_subcats.rename(columns={'RDSubCategoryName_Agg': 'RDSubCategories'}), 
                                         left_on='Id_str', right_on='CompanyMaster_FK_ID', how='left')
            company_df = company_df.drop(columns=['CompanyMaster_FK_ID', 'Id_str'])
        
        # Add HasRDFacility flag
        company_df['HasRDFacility'] = company_df['RDFacilityCount'].fillna(0) > 0
    else:
        company_df['HasRDFacility'] = False
        company_df['RDFacilityCount'] = 0
        company_df['RDCategories'] = ''
        company_df['RDSubCategories'] = ''
    
    # Test Facility aggregation
    if not test_fac_df.empty and 'CompanyMaster_FK_ID' in test_fac_df.columns and 'Id' in company_df.columns:
        # Count test facilities
        test_counts = test_fac_df.groupby('CompanyMaster_FK_ID').size().reset_index(name='TestFacilityCount')
        test_counts['CompanyMaster_FK_ID'] = test_counts['CompanyMaster_FK_ID'].astype(str)
        company_df['Id_str'] = company_df['Id'].astype(str)
        company_df = company_df.merge(test_counts, left_on='Id_str', right_on='CompanyMaster_FK_ID', how='left')
        company_df = company_df.drop(columns=['CompanyMaster_FK_ID', 'Id_str'])
        
        # Aggregate test categories
        if 'CategoryName' in test_fac_df.columns:
            test_cats = aggregate_text(test_fac_df, 'CompanyMaster_FK_ID', 'CategoryName')
            test_cats['CompanyMaster_FK_ID'] = test_cats['CompanyMaster_FK_ID'].astype(str)
            company_df['Id_str'] = company_df['Id'].astype(str)
            company_df = company_df.merge(test_cats.rename(columns={'CategoryName_Agg': 'TestCategories'}), 
                                         left_on='Id_str', right_on='CompanyMaster_FK_ID', how='left')
            company_df = company_df.drop(columns=['CompanyMaster_FK_ID', 'Id_str'])
        
        # Aggregate test subcategories
        if 'SubCategoryName' in test_fac_df.columns:
            test_subcats = aggregate_text(test_fac_df, 'CompanyMaster_FK_ID', 'SubCategoryName')
            test_subcats['CompanyMaster_FK_ID'] = test_subcats['CompanyMaster_FK_ID'].astype(str)
            company_df['Id_str'] = company_df['Id'].astype(str)
            company_df = company_df.merge(test_subcats.rename(columns={'SubCategoryName_Agg': 'TestSubCategories'}), 
                                         left_on='Id_str', right_on='CompanyMaster_FK_ID', how='left')
            company_df = company_df.drop(columns=['CompanyMaster_FK_ID', 'Id_str'])
        
        # Add HasTestFacility flag
        company_df['HasTestFacility'] = company_df['TestFacilityCount'].fillna(0) > 0
    else:
        company_df['HasTestFacility'] = False
        company_df['TestFacilityCount'] = 0
        company_df['TestCategories'] = ''
        company_df['TestSubCategories'] = ''
    
    # Fill NaN values with defaults
    company_df = company_df.fillna({
        'CertificationCount': 0,
        'ProductCount': 0,
        'RDFacilityCount': 0,
        'TestFacilityCount': 0,
        'CertificationTypes': '',
        'ProductNames': '',
        'ProductCategories': '',
        'RDCategories': '',
        'RDSubCategories': '',
        'TestCategories': '',
        'TestSubCategories': ''
    })
    
    return company_df


def build_certification_detail_view(inputs: Path) -> pd.DataFrame:
    """Build CertificationDetail view with resolved company and certification type names."""
    
    # Helper function to read CSV (copy from build_views_pandas.py)
    def _read_csv(p: Path) -> pd.DataFrame:
        if not p.exists():
            return pd.DataFrame()
        for encoding in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
            try:
                return pd.read_csv(p, dtype=str, encoding=encoding).fillna("")
            except (UnicodeDecodeError, Exception):
                continue
        for encoding in ['utf-8', 'latin-1', 'cp1252']:
            try:
                return pd.read_csv(p, dtype=str, sep=";", engine="python", encoding=encoding).fillna("")
            except Exception:
                continue
        return pd.DataFrame()
    
    # Helper function to find file (copy from build_views_pandas.py)
    def _find_file(inputs: Path, name_candidates):
        for nm in name_candidates:
            p = inputs / nm
            if p.exists():
                return p
        all_csvs = list(inputs.glob("*.csv"))
        lower_index = {f.name.lower(): f for f in all_csvs}
        for nm in name_candidates:
            nm_l = nm.lower()
            if nm_l in lower_index:
                return lower_index[nm_l]
            for k, f in lower_index.items():
                if nm_l in k:
                    return f
        return None
    
    # Helper to ensure FK column
    def _ensure_fk(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        if "CompanyMaster_FK_ID" in df.columns:
            return df
        for alt in ("CompanyID", "CompanyId", "Id", "MasterId", "CompanyMasterId"):
            if alt in df.columns:
                return df.rename(columns={alt: "CompanyMaster_FK_ID"})
        return df
    
    # Find certification file
    p = _find_file(inputs, [
        "dbo.CompanyCertificationDetail.csv",
        "CompanyCertificationDetail.csv",
        "CompanyCertification.csv",
    ])
    if not p:
        return pd.DataFrame(columns=[
            "CompanyRefNo", "CompanyName", "Certification_Type",
            "Certificate_No", "Certificate_StartDate", "Certificate_EndDate", "Cert_Type"
        ])
    
    df = _read_csv(p)
    df = _ensure_fk(df)
    
    # Load master tables for resolution
    company_master = _read_csv(inputs / "dbo.CompanyMaster.csv")
    cert_type_master = _read_csv(inputs / "dbo.CertificationTypeMaster.csv")
    
    # Resolve CompanyName from CompanyMaster_FK_ID
    if not company_master.empty and 'CompanyMaster_FK_ID' in df.columns:
        company_master_renamed = company_master.rename(columns={'Id': 'CompanyMaster_FK_ID'})
        cols_to_merge = ['CompanyMaster_FK_ID']
        if 'CompanyRefNo' in company_master.columns:
            cols_to_merge.append('CompanyRefNo')
        if 'CompanyName' in company_master.columns:
            cols_to_merge.append('CompanyName')
        
        if len(cols_to_merge) > 1:
            df = df.merge(
                company_master_renamed[cols_to_merge],
                on='CompanyMaster_FK_ID',
                how='left'
            )
    
    # Resolve Cert_Type from CertificateType_Fk_Id
    if not cert_type_master.empty and 'CertificateType_Fk_Id' in df.columns:
        cert_type_master_renamed = cert_type_master.rename(columns={'Id': 'CertificateType_Fk_Id'})
        if 'Cert_Type' in cert_type_master.columns:
            df = df.merge(
                cert_type_master_renamed[['CertificateType_Fk_Id', 'Cert_Type']],
                on='CertificateType_Fk_Id',
                how='left'
            )
    
    df = df.fillna("")
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


def build_rd_facility_details_view(inputs: Path) -> pd.DataFrame:
    """Build RDFacilityDetails view with resolved company and R&D category names."""
    
    # Find R&D facility file
    p = _find_file(inputs, [
        "dbo.CompanyRDFacility.csv",
        "CompanyRDFacility.csv",
    ])
    if not p:
        return pd.DataFrame(columns=[
            "CompanyMaster_FK_ID", "CompanyName", "IDMId", "CompanyRefNo",
            "RDCategoryName", "RDSubCategoryName"
        ])
    
    df = _read_csv(p)
    df = _ensure_fk(df)
    
    # Load master tables for resolution
    company_master = _read_csv(inputs / "dbo.CompanyMaster.csv")
    rd_category_master = _read_csv(inputs / "dbo.RDCategoryMaster.csv")
    rd_subcategory_master = _read_csv(inputs / "dbo.RDSubCategoryMaster.csv")
    
    # Resolve CompanyName from CompanyMaster_FK_ID
    if not company_master.empty and 'CompanyMaster_FK_ID' in df.columns:
        company_master_renamed = company_master.rename(columns={'Id': 'CompanyMaster_FK_ID'})
        cols_to_merge = ['CompanyMaster_FK_ID']
        if 'CompanyName' in company_master.columns:
            cols_to_merge.append('CompanyName')
        
        if len(cols_to_merge) > 1:
            df = df.merge(
                company_master_renamed[cols_to_merge],
                on='CompanyMaster_FK_ID',
                how='left'
            )
    
    # Resolve RDCategoryName from RDCategory_Fk_Id
    if not rd_category_master.empty and 'RDCategory_Fk_Id' in df.columns:
        rd_category_master_renamed = rd_category_master.rename(columns={'Id': 'RDCategory_Fk_Id'})
        if 'RDCategoryName' in rd_category_master.columns:
            df = df.merge(
                rd_category_master_renamed[['RDCategory_Fk_Id', 'RDCategoryName']],
                on='RDCategory_Fk_Id',
                how='left'
            )
    
    # Resolve RDSubCategoryName from RDSubCategory_Fk_Id
    if not rd_subcategory_master.empty and 'RDSubCategory_Fk_Id' in df.columns:
        rd_subcategory_master_renamed = rd_subcategory_master.rename(columns={'Id': 'RDSubCategory_Fk_Id'})
        if 'RDSubCategoryName' in rd_subcategory_master.columns:
            df = df.merge(
                rd_subcategory_master_renamed[['RDSubCategory_Fk_Id', 'RDSubCategoryName']],
                on='RDSubCategory_Fk_Id',
                how='left'
            )
    
    df = df.fillna("")
    return df


def build_test_facility_details_view(inputs: Path) -> pd.DataFrame:
    """Build TestFacilityDetails view with resolved company and test facility category names."""
    
    # Find Test facility file
    p = _find_file(inputs, [
        "dbo.CompanyTestFacility.csv",
        "CompanyTestFacility.csv",
    ])
    if not p:
        return pd.DataFrame(columns=[
            "CompanyMaster_FK_ID", "CompanyName", "CompanyRefNo", "TestDetails",
            "IsNablAccredited", "CategoryName", "SubCategoryName"
        ])
    
    df = _read_csv(p)
    df = _ensure_fk(df)
    
    # Load master tables for resolution
    company_master = _read_csv(inputs / "dbo.CompanyMaster.csv")
    test_category_master = _read_csv(inputs / "dbo.TestFacilityCategoryMaster.csv")
    test_subcategory_master = _read_csv(inputs / "dbo.TestFacilitySubCategoryMaster.csv")
    
    # Resolve CompanyName from CompanyMaster_FK_ID
    if not company_master.empty and 'CompanyMaster_FK_ID' in df.columns:
        company_master_renamed = company_master.rename(columns={'Id': 'CompanyMaster_FK_ID'})
        cols_to_merge = ['CompanyMaster_FK_ID']
        if 'CompanyName' in company_master.columns:
            cols_to_merge.append('CompanyName')
        
        if len(cols_to_merge) > 1:
            df = df.merge(
                company_master_renamed[cols_to_merge],
                on='CompanyMaster_FK_ID',
                how='left'
            )
    
    # Resolve CategoryName from TestFacilityCategory_Fk_Id
    if not test_category_master.empty and 'TestFacilityCategory_Fk_Id' in df.columns:
        test_category_master_renamed = test_category_master.rename(columns={'Id': 'TestFacilityCategory_Fk_Id'})
        if 'CategoryName' in test_category_master.columns:
            df = df.merge(
                test_category_master_renamed[['TestFacilityCategory_Fk_Id', 'CategoryName']],
                on='TestFacilityCategory_Fk_Id',
                how='left'
            )
    
    # Resolve SubCategoryName from TestFacilitySubCategory_Fk_id
    if not test_subcategory_master.empty and 'TestFacilitySubCategory_Fk_id' in df.columns:
        test_subcategory_master_renamed = test_subcategory_master.rename(columns={'Id': 'TestFacilitySubCategory_Fk_id'})
        if 'SubCategoryName' in test_subcategory_master.columns:
            df = df.merge(
                test_subcategory_master_renamed[['TestFacilitySubCategory_Fk_id', 'SubCategoryName']],
                on='TestFacilitySubCategory_Fk_id',
                how='left'
            )
    
    df = df.fillna("")
    return df


def build_product_details_view(inputs: Path) -> pd.DataFrame:
    """Build ProductDetails view with resolved company, product type, defence platform, and PTA names."""
    
    # Find Products file
    p = _find_file(inputs, [
        "dbo.CompanyProducts.csv",
        "CompanyProducts.csv",
    ])
    if not p:
        return pd.DataFrame(columns=[
            "CompanyMaster_FK_ID", "CompanyName", "CompanyRefNo", "ProductName",
            "ProductDesc", "NSNNumber", "HSNCode", "FutureExpansion",
            "AnnualProductionCapacity", "ProductCertificateDet", "ProductTypeName",
            "Name_of_Defence_Platform", "PTAName", "SalientFeature", "PARTNo",
            "Remarks", "ItemExported", "OtherDefencePlatform", "OtherTypeProduct", "OtherPTA"
        ])
    
    df = _read_csv(p)
    df = _ensure_fk(df)
    
    # Load master tables for resolution
    company_master = _read_csv(inputs / "dbo.CompanyMaster.csv")
    product_type_master = _read_csv(inputs / "dbo.ProductTypeMaster.csv")
    defence_platform_master = _read_csv(inputs / "dbo.DefencePlatformMaster.csv")
    pta_master = _read_csv(inputs / "dbo.PlatformTechAreaMaster.csv")
    
    # Resolve CompanyName from CompanyMaster_FK_ID
    if not company_master.empty and 'CompanyMaster_FK_ID' in df.columns:
        company_master_renamed = company_master.rename(columns={'Id': 'CompanyMaster_FK_ID'})
        cols_to_merge = ['CompanyMaster_FK_ID']
        if 'CompanyName' in company_master.columns:
            cols_to_merge.append('CompanyName')
        
        if len(cols_to_merge) > 1:
            df = df.merge(
                company_master_renamed[cols_to_merge],
                on='CompanyMaster_FK_ID',
                how='left'
            )
    
    # Resolve ProductTypeName from ProductType_Fk_Id
    if not product_type_master.empty and 'ProductType_Fk_Id' in df.columns:
        product_type_master_renamed = product_type_master.rename(columns={'Id': 'ProductType_Fk_Id'})
        if 'ProductTypeName' in product_type_master.columns:
            df = df.merge(
                product_type_master_renamed[['ProductType_Fk_Id', 'ProductTypeName']],
                on='ProductType_Fk_Id',
                how='left'
            )
    
    # Resolve Name_of_Defence_Platform from DefencePlatform_Fk_Id
    if not defence_platform_master.empty and 'DefencePlatform_Fk_Id' in df.columns:
        defence_platform_master_renamed = defence_platform_master.rename(columns={'Id': 'DefencePlatform_Fk_Id'})
        if 'Name_of_Defence_Platform' in defence_platform_master.columns:
            df = df.merge(
                defence_platform_master_renamed[['DefencePlatform_Fk_Id', 'Name_of_Defence_Platform']],
                on='DefencePlatform_Fk_Id',
                how='left'
            )
    
    # Resolve PTAName from PTAType_Fk_Id
    if not pta_master.empty and 'PTAType_Fk_Id' in df.columns:
        pta_master_renamed = pta_master.rename(columns={'Id': 'PTAType_Fk_Id'})
        if 'PTAName' in pta_master.columns:
            df = df.merge(
                pta_master_renamed[['PTAType_Fk_Id', 'PTAName']],
                on='PTAType_Fk_Id',
                how='left'
            )
    
    df = df.fillna("")
    return df


def build_turnover_details_view(inputs: Path) -> pd.DataFrame:
    """Build TurnOverDetails view with resolved company name and year."""
    
    # Find TurnOver file
    p = _find_file(inputs, [
        "dbo.CompanyTurnOver.csv",
        "CompanyTurnOver.csv",
    ])
    if not p:
        return pd.DataFrame(columns=[
            "Company_FK_Id", "CompanyName", "Year", "Amount"
        ])
    
    df = _read_csv(p)
    # Note: This table uses Company_FK_Id instead of CompanyMaster_FK_ID
    
    # Load master tables for resolution
    company_master = _read_csv(inputs / "dbo.CompanyMaster.csv")
    year_master = _read_csv(inputs / "dbo.YearMaster.csv")
    
    # Resolve CompanyName from Company_FK_Id
    if not company_master.empty and 'Company_FK_Id' in df.columns:
        company_master_renamed = company_master.rename(columns={'Id': 'Company_FK_Id'})
        cols_to_merge = ['Company_FK_Id']
        if 'CompanyName' in company_master.columns:
            cols_to_merge.append('CompanyName')
        
        if len(cols_to_merge) > 1:
            df = df.merge(
                company_master_renamed[cols_to_merge],
                on='Company_FK_Id',
                how='left'
            )
    
    # Resolve Year from YearId
    if not year_master.empty and 'YearId' in df.columns:
        year_master_renamed = year_master.rename(columns={'Id': 'YearId'})
        if 'Year' in year_master.columns:
            df = df.merge(
                year_master_renamed[['YearId', 'Year']],
                on='YearId',
                how='left'
            )
    
    df = df.fillna("")
    return df


# --------------------------- Merged outputs ---------------------------

def write_merged_company_csv(out_dir: Path, company: pd.DataFrame, cert: pd.DataFrame, prod: pd.DataFrame) -> Path:
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
    prod_cols = [c for c in ["ProductName","Category","Description"] if c in prod.columns]

    cagg = agg_join(cert, fk, cert_cols) if cert_cols else pd.DataFrame(columns=[fk])
    pagg = agg_join(prod, fk, prod_cols) if prod_cols else pd.DataFrame(columns=[fk])

    C = company.copy()
    if "Id" not in C.columns:
        raise SystemExit("CompanyDetail must contain an 'Id' column after normalization.")
    if not cagg.empty: C = C.merge(cagg.rename(columns={fk: "Id"}), on="Id", how="left")
    if not pagg.empty: C = C.merge(pagg.rename(columns={fk: "Id"}), on="Id", how="left")

    # selection (optional; only if you added a companydetailenriched list)
    out_path = out_dir / "MergedCompanyView.csv"
    C.fillna("").to_csv(out_path, index=False)
    return out_path


def write_merged_company_json(out_dir: Path, company: pd.DataFrame, cert: pd.DataFrame, prod: pd.DataFrame) -> None:
    """Write per-company JSON + JSONL with nested arrays (certifications/products)."""
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
            "is_government": row.get("is_government", False),
            "is_private": row.get("is_private", False),
            "is_msme": row.get("is_msme", False),
            "certifications": cert_by.get(cid, []),
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

    # 1) Build base CompanyDetail view
    print("• Building CompanyDetail ...")
    df_company = build_company_detail(IN)

    print("• Building CertificationDetail ...")
    df_cert = build_certification_detail_view(IN)
    df_cert = _apply_field_selection(df_cert, "CertificationDetail")
    df_cert.to_csv(OUT / "CertificationDetail.csv", index=False)
    print(f"  -> {OUT/'CertificationDetail.csv'} ({len(df_cert)} rows)")

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

    print("• Building RDFacilityDetails ...")
    df_rd_facility = build_rd_facility_details_view(IN)
    df_rd_facility = _apply_field_selection(df_rd_facility, "RDFacilityDetails")
    df_rd_facility.to_csv(OUT / "RDFacilityDetails.csv", index=False)
    print(f"  -> {OUT/'RDFacilityDetails.csv'} ({len(df_rd_facility)} rows)")

    print("• Building TestFacilityDetails ...")
    df_test_facility = build_test_facility_details_view(IN)
    df_test_facility = _apply_field_selection(df_test_facility, "TestFacilityDetails")
    df_test_facility.to_csv(OUT / "TestFacilityDetails.csv", index=False)
    print(f"  -> {OUT/'TestFacilityDetails.csv'} ({len(df_test_facility)} rows)")

    print("• Building ProductDetails ...")
    df_product_details = build_product_details_view(IN)
    df_product_details = _apply_field_selection(df_product_details, "ProductDetails")
    df_product_details.to_csv(OUT / "ProductDetails.csv", index=False)
    print(f"  -> {OUT/'ProductDetails.csv'} ({len(df_product_details)} rows)")

    print("• Building TurnOverDetails ...")
    df_turnover = build_turnover_details_view(IN)
    df_turnover = _apply_field_selection(df_turnover, "TurnOverDetails")
    df_turnover.to_csv(OUT / "TurnOverDetails.csv", index=False)
    print(f"  -> {OUT/'TurnOverDetails.csv'} ({len(df_turnover)} rows)")

    # Enrich CompanyDetail with aggregated data from certifications, products, and facilities
    print("• Enriching CompanyDetail with aggregated facility and product information...")
    df_company = _enrich_with_aggregated_data(df_company, df_cert, df_prod, df_rd_facility, df_test_facility)
    
    # Apply field selection and save enriched CompanyDetail
    df_company = _apply_field_selection(df_company, "CompanyDetail")
    df_company.to_csv(OUT / "CompanyDetail.csv", index=False)
    print(f"  -> {OUT/'CompanyDetail.csv'} ({len(df_company)} rows)")
    
    # Report statistics
    if 'is_government' in df_company.columns:
        govt_count = df_company['is_government'].sum()
        print(f"     ℹ  {govt_count} government companies")
    if 'is_msme' in df_company.columns:
        msme_count = df_company['is_msme'].sum()
        print(f"     ℹ  {msme_count} MSME companies")
    if 'HasRDFacility' in df_company.columns:
        rd_count = df_company['HasRDFacility'].sum()
        print(f"     ℹ  {rd_count} companies with R&D facilities")
    if 'HasTestFacility' in df_company.columns:
        test_count = df_company['HasTestFacility'].sum()
        print(f"     ℹ  {test_count} companies with Test facilities")
    if 'HasCertifications' in df_company.columns:
        cert_count = df_company['HasCertifications'].sum()
        print(f"     ℹ  {cert_count} companies with Certifications")
    if 'HasProducts' in df_company.columns:
        prod_count = df_company['HasProducts'].sum()
        print(f"     ℹ  {prod_count} companies with Products")

    # 2) Merged company outputs (CSV + JSON + JSONL)
    print("• Writing merged company CSV ...")
    merged_csv = write_merged_company_csv(OUT, df_company, df_cert, df_prod)
    print(f"  -> {merged_csv}")

    print("• Writing merged company JSON/JSONL ...")
    write_merged_company_json(OUT, df_company, df_cert, df_prod)
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

    print("\n Done. Views written to:", OUT.resolve())

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        sys.exit(130)

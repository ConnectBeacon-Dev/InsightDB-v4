#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_views_pandas.py (dbo-aware, robust CSV reader, optional-column safe)
Rebuilds denormalized "views" CSVs from normalized inputs for comprehensive querying.
- Supports both 'Name.csv' and 'dbo.Name.csv' (case-insensitive).
- Robust CSV loader tries multiple encodings & separators, skips bad lines.
- Tolerates missing optional inputs/columns.

Outputs:
CompanyDetail.csv
Certification.csv
Products.csv
Facilities.csv
Supplies.csv        (only if CompanySupplies exists)
TurnOver.csv
Employees.csv       (only if CompanyEmployees exists)
"""

import argparse
import pandas as pd
from pathlib import Path

# -------- helpers (robust CSV reader) --------
def _read_csv_robust(path):
        """
        Tries multiple encodings and separators; prefers python engine for sniffing.
        Skips bad lines if present. Returns a pandas DataFrame.
        """
        # Quick BOM sniff
        with open(path, "rb") as fb:
            head = fb.read(4)
        bom_encoding = None
        if head.startswith(b"\xff\xfe"):
            bom_encoding = "utf-16le"
        elif head.startswith(b"\xfe\xff"):
            bom_encoding = "utf-16be"
        elif head.startswith(b"\xef\xbb\xbf"):
            bom_encoding = "utf-8-sig"

        encodings = ([bom_encoding] if bom_encoding else []) + [
            "utf-8", "utf-8-sig", "cp1252", "latin-1", "utf-16", "utf-16le", "utf-16be"
        ]
        seps = [None, ",", ";", "\t", "|"]  # None => auto-sniff (engine='python')

        last_err = None
        for enc in encodings:
            if not enc:
                continue
            for sep in seps:
                try:
                    kwargs = {"encoding": enc, "engine": "python"}
                    kwargs["sep"] = sep  # sep=None triggers sniff
                    try:
                        return pd.read_csv(path, on_bad_lines="skip", **kwargs)
                    except TypeError:
                        return pd.read_csv(path, error_bad_lines=False, **kwargs)  # older pandas
                except Exception as e:
                    last_err = e
                    continue
        raise RuntimeError(f"Failed reading {path}: {last_err}")

def find_csv(IN: Path, base: str, required=False):
        """
        Looks for both 'base.csv' and 'dbo.<base>.csv' (case-insensitive).
        Reads robustly with multiple encodings & separator sniffing.
        """
        candidates = [
            IN / f"{base}.csv",
            IN / f"dbo.{base}.csv",
            IN / f"{base}.CSV",
            IN / f"dbo.{base}.CSV",
        ]
        for c in candidates:
            if c.exists():
                return _read_csv_robust(c)
        if required:
            raise FileNotFoundError(f"Missing required input: {base}.csv (or dbo.{base}.csv) in {IN}")
        return pd.DataFrame()

def write_csv(df, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False)

# helper: ensure columns exist
def ensure_cols(df, cols):
        for c in cols:
            if c not in df.columns:
                df[c] = None
        return df

# helper: coalesce company foreign key column
def coalesce_company_fk(df, out_col="CompanyMaster_FK_ID"):
        """
        Rename the first matching company id column to out_col.
        If none found, create an empty column so downstream never KeyErrors.
        """
        candidates = [
            "CompanyId","CompanyID","Company_Id",
            "CompanyMasterId","CompanyMasterID",
            "Id","RefNo","RefID"
        ]
        for c in candidates:
            if c in df.columns:
                return df.rename(columns={c: out_col})
        df[out_col] = None
        return df

def main():
        ap = argparse.ArgumentParser()
        ap.add_argument("--in", dest="inp", required=True, help="Folder with normalized input CSVs (supports dbo.*)")
        ap.add_argument("--out", dest="out", required=True, help="Folder to write denormalized view CSVs")
        args = ap.parse_args()
        IN = Path(args.inp); OUT = Path(args.out)

        # ---------- Load inputs (dbo-aware) ----------
        CM   = find_csv(IN, "CompanyMaster", required=True)
        # Org type (two spellings)
        OTM  = find_csv(IN, "OrganizationTypeMaster")
        if OTM.empty:
            OTM = find_csv(IN, "OrganisationTypeMaster")
        SMM  = find_csv(IN, "ScaleMaster")
        CSC  = find_csv(IN, "CompanyScale")             # optional: CompanyId, ScaleId, FromDate, ToDate
        CSM  = find_csv(IN, "CompanyScaleMaster")       # optional
        CNT  = find_csv(IN, "CountryMaster")
        ADDR = find_csv(IN, "Address")
        CITY = find_csv(IN, "CityMaster")
        ST   = find_csv(IN, "StateMaster")
        CCON = find_csv(IN, "CompanyContacts")          # optional

        IDM  = find_csv(IN, "IndustryDomainMaster")
        ISM  = find_csv(IN, "IndustrySubdomainMaster")
        CDM  = find_csv(IN, "CompanyDomainMap")
        CCE  = find_csv(IN, "CompanyCoreExpertise")
        CCEM = find_csv(IN, "CompanyCoreExpertiseMaster")

        CTM  = find_csv(IN, "CertificationTypeMaster")
        CCD  = find_csv(IN, "CompanyCertificationDetail")

        PCM  = find_csv(IN, "ProductCategoryMaster")
        PTM  = find_csv(IN, "ProductTypeMaster")
        CP   = find_csv(IN, "CompanyProducts")
        DPM  = find_csv(IN, "DefencePlatformMaster")
        PTAM = find_csv(IN, "PlatformTechAreaMaster")
        PPM  = find_csv(IN, "ProductPlatformMap")       # may not exist

        CRD  = find_csv(IN, "CompanyRDFacility")
        RDC  = find_csv(IN, "RDCategoryMaster")
        RDS  = find_csv(IN, "RDSubCategoryMaster")

        CTF  = find_csv(IN, "CompanyTestFacility")
        TFC  = find_csv(IN, "TestFacilityCategoryMaster")
        TFS  = find_csv(IN, "TestFacilitySubCategoryMaster")
        ACCR = find_csv(IN, "AccreditationMaster")

        CMFG = find_csv(IN, "CompanyManufacturingFacility")

        CSUP = find_csv(IN, "CompanySupplies")          # optional
        BAL  = find_csv(IN, "BuyerAliasMaster")         # optional
        CTO  = find_csv(IN, "CompanyTurnOver")
        CEMP = find_csv(IN, "CompanyEmployees")         # optional

        # ---------- CompanyDetail.csv ----------
        df = CM.copy()

        # Normalize common column variants
        ren = {
            "CompanyId": "Id",
            "CompanyID": "Id",
            "CompanyName": "Name",
            "OrgTypeID": "OrgTypeId",
            "OrganisationTypeID": "OrgTypeId",
            "OrganizationTypeID": "OrgTypeId",
            "ScaleID": "ScaleId",
            "CountryID": "CountryId",
            "PinCode": "Pincode",
        }
        for k, v in ren.items():
            if k in df.columns and v not in df.columns:
                df = df.rename(columns={k: v})

        # OrgType join
        if "OrgTypeId" in df.columns and not OTM.empty:
            otm = OTM.copy()
            if "OrgType" not in otm.columns:
                for alt in ["Name", "Type", "OrganisationType", "OrganizationType"]:
                    if alt in otm.columns:
                        otm = otm.rename(columns={alt: "OrgType"}); break
            if "Id" not in otm.columns:
                for alt in ["OrgTypeId", "OrganisationTypeId", "OrganizationTypeId", "Code", "Key"]:
                    if alt in otm.columns:
                        otm = otm.rename(columns={alt: "Id"}); break
            if {"Id","OrgType"}.issubset(otm.columns):
                df = df.merge(otm[["Id","OrgType"]].rename(columns={"Id":"OrgTypeId"}), on="OrgTypeId", how="left")

        # Scale: from CompanyScale (dated) or ScaleId or CompanyScaleMaster
        if not CSC.empty and {"CompanyId","ScaleId"}.issubset(CSC.columns):
            latest = CSC.sort_values(["CompanyId","ToDate"], na_position="last").drop_duplicates("CompanyId", keep="last")
            df = df.merge(latest.rename(columns={"CompanyId":"Id","ScaleId":"ScaleId_join"}), on="Id", how="left")
            if not SMM.empty:
                smm = SMM.copy()
                if "Scale" not in smm.columns:
                    for alt in ["Name","ScaleName"]:
                        if alt in smm.columns: smm = smm.rename(columns={alt:"Scale"}); break
                df = df.merge(smm.rename(columns={"Id":"ScaleId_join"}), on="ScaleId_join", how="left")
        elif "ScaleId" in df.columns and not SMM.empty:
            smm = SMM.copy()
            if "Scale" not in smm.columns:
                for alt in ["Name","ScaleName"]:
                    if alt in smm.columns: smm = smm.rename(columns={alt:"Scale"}); break
            df = df.merge(smm.rename(columns={"Id":"ScaleId"}), on="ScaleId", how="left")
        elif not CSM.empty and {"CompanyId","ScaleId"}.issubset(CSM.columns) and not SMM.empty:
            map_df = CSM.rename(columns={"CompanyId":"Id"})
            smm = SMM.copy()
            if "Scale" not in smm.columns:
                for alt in ["Name","ScaleName"]:
                    if alt in smm.columns: smm = smm.rename(columns={alt:"Scale"}); break
            df = df.merge(map_df[["Id","ScaleId"]].drop_duplicates("Id"), on="Id", how="left")
            df = df.merge(smm.rename(columns={"Id":"ScaleId"}), on="ScaleId", how="left")

        # Country name
        if "CountryId" in df.columns and not CNT.empty:
            cn = CNT.copy()
            if "CountryName" not in cn.columns:
                for alt in ["Name","Country"]:
                    if alt in cn.columns: cn = cn.rename(columns={alt:"CountryName"}); break
            df = df.merge(cn.rename(columns={"Id":"CountryId"}), on="CountryId", how="left")

        # City/State from CompanyMaster if present (fallback when no Address tables)
        if "City" not in df.columns:
            for alt in ["CityName","Town","Locality"]:
                if alt in df.columns: df = df.rename(columns={alt:"City"}); break
        if "State" not in df.columns:
            for alt in ["StateName","Province","Region"]:
                if alt in df.columns: df = df.rename(columns={alt:"State"}); break

        # Enrich using Address/City/State if provided
        if not ADDR.empty:
            ad = ADDR.copy()
            if "AddressType" in ad.columns:
                ad = ad.sort_values(["CompanyId","AddressType"]).drop_duplicates("CompanyId", keep="first")
            ad = ad.rename(columns={"CompanyId":"Id"})
            if "CityId" in ad.columns and not CITY.empty:
                city = CITY.rename(columns={"Id":"CityId"})
                if "City" not in city.columns:
                    for alt in ["Name"]:
                        if alt in city.columns: city = city.rename(columns={alt:"City"}); break
                ad = ad.merge(city[["CityId","City"]], on="CityId", how="left")
            if "StateId" in ad.columns and not ST.empty:
                st = ST.rename(columns={"Id":"StateId"})
                if "State" not in st.columns:
                    for alt in ["Name"]:
                        if alt in st.columns: st = st.rename(columns={alt:"State"}); break
                ad = ad.merge(st[["StateId","State"]], on="StateId", how="left")
            # Flatten address lines
            ad["Address"] = ad.get("Line1","").astype(str).fillna("")
            for c in ["Line2","Line3","Line4"]:
                if c in ad.columns:
                    ad["Address"] = ad["Address"] + (" " + ad[c].astype(str))
            keep_ad = ["Id","Address","City","State","Pincode","Lat","Lng"]
            for k in keep_ad:
                if k not in ad.columns: ad[k] = None
            df = df.merge(ad[keep_ad].drop_duplicates("Id"), on="Id", how="left", suffixes=("","_addr"))
            if "City_addr" in df.columns:
                df["City"] = df["City"].fillna(df["City_addr"])
            if "State_addr" in df.columns:
                df["State"] = df["State"].fillna(df["State_addr"])

        # Domains/Subdomains via mapping table if provided
        if not CDM.empty:
            dom = CDM.rename(columns={"CompanyId":"Id"})
            if "DomainId" in dom.columns and not IDM.empty:
                d = IDM.rename(columns={"Id":"DomainId"})
                if "Domain" not in d.columns:
                    for alt in ["DomainName","Name","IndustryDomain"]:
                        if alt in d.columns: d = d.rename(columns={alt:"Domain"}); break
                dom = dom.merge(d[["DomainId","Domain"]].rename(columns={"Domain":"IndustryDomain"}), on="DomainId", how="left")
            if "SubdomainId" in dom.columns and not ISM.empty:
                s = ISM.rename(columns={"Id":"SubdomainId"})
                if "Subdomain" not in s.columns:
                    for alt in ["SubDomain","Name","IndustrySubdomain"]:
                        if alt in s.columns: s = s.rename(columns={alt:"Subdomain"}); break
                dom = dom.merge(s[["SubdomainId","Subdomain"]].rename(columns={"Subdomain":"IndustrySubdomain"}), on="SubdomainId", how="left")
            agg = dom.groupby("Id").agg({
                "IndustryDomain": lambda x: "; ".join(sorted(set([t for t in x.dropna().astype(str) if t]))),
                "IndustrySubdomain": lambda x: "; ".join(sorted(set([t for t in x.dropna().astype(str) if t]))),
            }).reset_index()
            df = df.merge(agg, on="Id", how="left")

        # Core expertise aggregation (if CompanyCoreExpertise + Master present)
        if not CCE.empty and not CCEM.empty:
            cem = CCEM.copy()
            if "CoreName" not in cem.columns:
                for alt in ["Name","Expertise","Core"]:
                    if alt in cem.columns: cem = cem.rename(columns={alt:"CoreName"}); break
            ce = CCE.rename(columns={"CompanyId":"Id","CoreId":"CoreId"}).merge(
                cem.rename(columns={"Id":"CoreId","CoreName":"CoreExpert"}),
                on="CoreId", how="left"
            )
            agg = ce.groupby("Id")["CoreExpert"].apply(
                lambda s: "; ".join(sorted(set([t for t in s.dropna().astype(str) if t])))
            ).reset_index().rename(columns={"Id":"Id","CoreExpert":"CoreExpertise"})
            df = df.merge(agg, on="Id", how="left")

        # Contacts aggregation (optional)
        if not CCON.empty:
            con = CCON.rename(columns={"CompanyId":"Id"})
            con_agg = con.groupby("Id").agg({
                "Email": lambda s: "; ".join(sorted(set([x for x in s.dropna().astype(str) if x]))),
                "Phone": lambda s: "; ".join(sorted(set([x for x in s.dropna().astype(str) if x]))),
            }).reset_index()
            df = df.merge(con_agg, on="Id", how="left")

        # --- Include ALL CompanyMaster fields except audit fields and null columns ---
        # Exclude audit/internal fields
        exclude_cols = ["CreatedDate", "CreatedBy", "IPAddress", "IsActive", "Final_Submit"]
        
        # Rename key columns for clarity
        df = df.rename(columns={
            "Name": "CompanyName",
            "CountryName": "Country"
        })
        
        # Drop completely null columns
        df = df.dropna(axis=1, how='all')
        
        # Drop excluded audit fields
        for col in exclude_cols:
            if col in df.columns:
                df = df.drop(columns=[col])
        
        out_company = df.drop_duplicates()

        write_csv(out_company, OUT/"CompanyDetail.csv")

        # ---------- Certification.csv ----------
        cert = CCD.copy()
        if not cert.empty:
            if "CompanyId" in cert.columns:
                cert = cert.rename(columns={"CompanyId":"CompanyMaster_FK_ID"})
            if not CTM.empty and "CertTypeId" in cert.columns:
                ctm = CTM.copy()
                if "CertificationType" not in ctm.columns and "Name" in ctm.columns:
                    ctm = ctm.rename(columns={"Name":"CertificationType"})
                cert = cert.merge(ctm.rename(columns={"Id":"CertTypeId"}), on="CertTypeId", how="left")
            keep = ["CompanyMaster_FK_ID","CertificationType","Number","Issuer","ValidFrom","ValidTo","Status"]
            for c in keep:
                if c not in cert.columns: cert[c] = None
            write_csv(cert[keep].drop_duplicates(), OUT/"Certification.csv")

        # ---------- Products.csv ----------
        prod = CP.copy()
        if not prod.empty:
            if "CompanyId" in prod.columns:
                prod = prod.rename(columns={"CompanyId":"CompanyMaster_FK_ID"})
            if not PTM.empty and "ProductTypeId" in prod.columns:
                ptm = PTM.copy()
                if "ProductType" not in ptm.columns:
                    for alt in ["Name","Type"]:
                        if alt in ptm.columns: ptm = ptm.rename(columns={alt:"ProductType"}); break
                prod = prod.merge(ptm.rename(columns={"Id":"ProductTypeId"}), on="ProductTypeId", how="left")
            if not PCM.empty and "CategoryId" in prod.columns:
                pcm = PCM.copy()
                if "Category" not in pcm.columns and "Name" in pcm.columns:
                    pcm = pcm.rename(columns={"Name":"Category"})
                prod = prod.merge(pcm.rename(columns={"Id":"CategoryId"}), on="CategoryId", how="left")

            # Platforms/TechArea via ProductPlatformMap (if available)
            if not PPM.empty and "ProductId" in prod.columns:
                pp = PPM.copy()
                if not DPM.empty and "PlatformId" in pp.columns:
                    dpm = DPM.copy()
                    if "DefencePlatform" not in dpm.columns:
                        for alt in ["Platform","Name"]:
                            if alt in dpm.columns: dpm = dpm.rename(columns={alt:"DefencePlatform"}); break
                    pp = pp.merge(dpm.rename(columns={"Id":"PlatformId"}), on="PlatformId", how="left")
                if not PTAM.empty and "TechAreaId" in pp.columns:
                    ta = PTAM.copy()
                    if "TechArea" not in ta.columns:
                        for alt in ["Name","Area"]:
                            if alt in ta.columns: ta = ta.rename(columns={alt:"TechArea"}); break
                    pp = pp.merge(ta.rename(columns={"Id":"TechAreaId"}), on="TechAreaId", how="left")
                agg = pp.groupby("ProductId").agg({
                    "DefencePlatform": lambda s: "; ".join(sorted(set([x for x in s.dropna().astype(str) if x]))),
                    "TechArea":       lambda s: "; ".join(sorted(set([x for x in s.dropna().astype(str) if x]))),
                }).reset_index()
                prod = prod.merge(agg, on="ProductId", how="left")

            for c in ["ProductName","Category","ProductType","Description","HSCode","IsConsumable","DefencePlatform","TechArea","ProductId"]:
                if c not in prod.columns: prod[c] = None
            keep = ["CompanyMaster_FK_ID","ProductId","ProductName","Category","ProductType","Description","HSCode","IsConsumable","DefencePlatform","TechArea"]
            write_csv(prod[keep].drop_duplicates(), OUT/"Products.csv")

        # ---------- Facilities.csv (R&D + TEST + MFG unified) ----------
        fac_parts = []

        # -------- R&D --------
        if not CRD.empty:
            x = CRD.copy()
            if "CompanyId" in x.columns:
                x = x.rename(columns={"CompanyId": "CompanyMaster_FK_ID"})
            x["FacilityType"] = "R&D"

            # RD category/subcategory joins (if ids exist)
            if "RDCategoryId" in x.columns and not RDC.empty:
                cat = RDC.rename(columns={"Id": "RDCategoryId"})
                if "RDCategory" not in cat.columns and "Name" in cat.columns:
                    cat = cat.rename(columns={"Name": "RDCategory"})
                x = x.merge(cat[["RDCategoryId", "RDCategory"]], on="RDCategoryId", how="left")

            if "RDSubCategoryId" in x.columns and not RDS.empty:
                sub = RDS.rename(columns={"Id": "RDSubCategoryId"})
                if "RDSubCategory" not in sub.columns and "Name" in sub.columns:
                    sub = sub.rename(columns={"Name": "RDSubCategory"})
                x = x.merge(sub[["RDSubCategoryId", "RDSubCategory"]], on="RDSubCategoryId", how="left")

            # Normalize column names expected in output
            if "RDCategory" in x.columns and "Category" not in x.columns:
                x = x.rename(columns={"RDCategory": "Category"})
            if "RDSubCategory" in x.columns and "SubCategory" not in x.columns:
                x = x.rename(columns={"RDSubCategory": "SubCategory"})

            # Facility name fallback (use whatever exists)
            if "FacilityName" not in x.columns:
                for alt in ["Facility", "Name", "LabName", "CentreName", "CenterName"]:
                    if alt in x.columns:
                        x = x.rename(columns={alt: "FacilityName"})
                        break

            # Make sure required columns exist
            x = ensure_cols(x, ["CompanyMaster_FK_ID", "FacilityType", "Category", "SubCategory", "FacilityName", "Accreditation"])
            fac_parts.append(x[["CompanyMaster_FK_ID", "FacilityType", "Category", "SubCategory", "FacilityName", "Accreditation"]])

        # -------- TEST --------
        if not CTF.empty:
            y = CTF.copy()
            if "CompanyId" in y.columns:
                y = y.rename(columns={"CompanyId": "CompanyMaster_FK_ID"})
            y["FacilityType"] = "TEST"

            if "TestCategoryId" in y.columns and not TFC.empty:
                tcat = TFC.rename(columns={"Id": "TestCategoryId"})
                if "TestCategory" not in tcat.columns and "Name" in tcat.columns:
                    tcat = tcat.rename(columns={"Name": "TestCategory"})
                y = y.merge(tcat[["TestCategoryId", "TestCategory"]], on="TestCategoryId", how="left")

            if "TestSubCategoryId" in y.columns and not TFS.empty:
                tsub = TFS.rename(columns={"Id": "TestSubCategoryId"})
                if "TestSubCategory" not in tsub.columns and "Name" in tsub.columns:
                    tsub = tsub.rename(columns={"Name": "TestSubCategory"})
                y = y.merge(tsub[["TestSubCategoryId", "TestSubCategory"]], on="TestSubCategoryId", how="left")

            # Normalize names
            if "TestCategory" in y.columns and "Category" not in y.columns:
                y = y.rename(columns={"TestCategory": "Category"})
            if "TestSubCategory" in y.columns and "SubCategory" not in y.columns:
                y = y.rename(columns={"TestSubCategory": "SubCategory"})

            # Facility name fallback
            if "FacilityName" not in y.columns:
                for alt in ["Facility", "Name", "LabName", "CentreName", "CenterName"]:
                    if alt in y.columns:
                        y = y.rename(columns={alt: "FacilityName"})
                        break

            # Accreditation pass-through if present under different names
            if "Accreditation" not in y.columns:
                for alt in ["AccreditationName", "AccreditationId", "Accreditation_code"]:
                    if alt in y.columns:
                        y["Accreditation"] = y[alt]
                        break

            y = ensure_cols(y, ["CompanyMaster_FK_ID", "FacilityType", "Category", "SubCategory", "FacilityName", "Accreditation"])
            fac_parts.append(y[["CompanyMaster_FK_ID", "FacilityType", "Category", "SubCategory", "FacilityName", "Accreditation"]])

        # -------- MFG (optional) --------
        if not CMFG.empty:
            z = CMFG.copy()
            if "CompanyId" in z.columns:
                z = z.rename(columns={"CompanyId": "CompanyMaster_FK_ID"})
            z["FacilityType"] = "MFG"
            if "Category" not in z.columns:
                z["Category"] = z.get("Process", "")
            if "SubCategory" not in z.columns:
                z["SubCategory"] = None
            if "FacilityName" not in z.columns:
                for alt in ["Facility", "Name", "Notes"]:
                    if alt in z.columns:
                        z = z.rename(columns={alt: "FacilityName"})
                        break
            z = ensure_cols(z, ["CompanyMaster_FK_ID", "FacilityType", "Category", "SubCategory", "FacilityName", "Accreditation"])
            fac_parts.append(z[["CompanyMaster_FK_ID", "FacilityType", "Category", "SubCategory", "FacilityName", "Accreditation"]])

        # Final write
        if fac_parts:
            FAC = pd.concat(fac_parts, ignore_index=True).drop_duplicates()
            write_csv(FAC, OUT/"Facilities.csv")

        # ---------- Supplies.csv (optional) ----------
        if not CSUP.empty:
            s = coalesce_company_fk(CSUP.copy(), out_col="CompanyMaster_FK_ID")
            if "BuyerAliasId" in s.columns and not BAL.empty:
                s = s.merge(BAL.rename(columns={"Id":"BuyerAliasId","CanonicalName":"CanonicalBuyer","Alias":"Alias"}), on="BuyerAliasId", how="left")
            for c in ["BuyerName","CanonicalBuyer","BuyerState","BuyerCity","ProductId","ProductName","Qty","UOM","PORef","PODate","ProgramName"]:
                if c not in s.columns: s[c] = None
            write_csv(s[["CompanyMaster_FK_ID","BuyerName","CanonicalBuyer","BuyerState","BuyerCity","ProductId","ProductName","Qty","UOM","PORef","PODate","ProgramName"]].drop_duplicates(), OUT/"Supplies.csv")

        # ---------- TurnOver.csv ----------
        if not CTO.empty:
            to = coalesce_company_fk(CTO.copy(), out_col="CompanyMaster_FK_ID")

            # Normalize FY / TurnoverCr names if needed
            if "FY" not in to.columns:
                for alt in ["FinancialYear","Year","FYYear","FiscalYear","FY_Yr"]:
                    if alt in to.columns:
                        to = to.rename(columns={alt:"FY"})
                        break
            if "TurnoverCr" not in to.columns:
                for alt in ["Turnover","Turnover_Cr","RevenueCr","Revenue","Turnover(INR Cr)","TurnoverInCr"]:
                    if alt in to.columns:
                        to = to.rename(columns={alt:"TurnoverCr"})
                        break

            # Ensure columns exist so selection cannot fail
            to = ensure_cols(to, ["CompanyMaster_FK_ID","FY","TurnoverCr"])

            write_csv(to[["CompanyMaster_FK_ID","FY","TurnoverCr"]].drop_duplicates(), OUT/"TurnOver.csv")

        # ---------- Employees.csv (optional) ----------
        if not CEMP.empty:
            e = coalesce_company_fk(CEMP.copy(), out_col="CompanyMaster_FK_ID")
            for c in ["FY","Headcount","EnggRatio"]:
                if c not in e.columns: e[c] = None
            write_csv(e[["CompanyMaster_FK_ID","FY","Headcount","EnggRatio"]].drop_duplicates(), OUT/"Employees.csv")

        # ---------- CompanyDetailEnriched.csv (NEW: with inference) ----------
        print("Building enriched company view with industry inference...")
        build_enriched_company_view(OUT)
        
        print(f"Views written to {OUT}")

def build_enriched_company_view(OUT: Path):
    """
    Creates CompanyDetailEnriched.csv with:
    - All company details
    - Inferred industry domain from products if empty
    - Aggregated counts (products, facilities, certifications)
    - Product/tech area summaries
    - Latest financial data
    """
# Load the views we just created
    company = pd.read_csv(OUT/"CompanyDetail.csv", dtype=str).fillna("")
    
    products = pd.DataFrame()
    if (OUT/"Products.csv").exists():
        products = pd.read_csv(OUT/"Products.csv", dtype=str).fillna("")
    
    facilities = pd.DataFrame()
    if (OUT/"Facilities.csv").exists():
        facilities = pd.read_csv(OUT/"Facilities.csv", dtype=str).fillna("")
    
    certifications = pd.DataFrame()
    if (OUT/"Certification.csv").exists():
        certifications = pd.read_csv(OUT/"Certification.csv", dtype=str).fillna("")
    
    turnover = pd.DataFrame()
    if (OUT/"TurnOver.csv").exists():
        turnover = pd.read_csv(OUT/"TurnOver.csv", dtype=str).fillna("")
    
    enriched = company.copy()
    
    # Ensure IndustryDomain column exists (might not exist if not in original data or joins)
    if "IndustryDomain" not in enriched.columns:
        enriched["IndustryDomain"] = ""
    
# --- INDUSTRY INFERENCE LOGIC ---
    if not products.empty and "CompanyMaster_FK_ID" in products.columns:
        # Infer industry from products for companies with empty IndustryDomain
        industry_keywords = {
            "Chemical & Petroleum Products": ["oil", "grease", "lubricant", "hydraulic", "petroleum", "chemical", "solvent", "coolant", "fluid"],
            "Electronics & Electrical": ["electronic", "circuit", "pcb", "sensor", "relay", "switch", "electrical", "cable", "wire"],
            "Mechanical Engineering": ["gear", "bearing", "shaft", "valve", "pump", "mechanical", "machine", "tool"],
            "Defence & Aerospace": ["ammunition", "missile", "radar", "armour", "military", "defence", "aerospace"],
            "Pharmaceuticals": ["drug", "medicine", "pharmaceutical", "api", "tablet", "injection", "vaccine"],
            "Textiles": ["fabric", "textile", "cloth", "yarn", "garment", "fiber"],
            "Automotive": ["automobile", "vehicle", "car", "truck", "engine", "automotive"],
            "IT & Software": ["software", "application", "system", "it", "computer", "digital"],
        }
        
        def infer_industry(row):
            if row["IndustryDomain"].strip():  # Already has industry
                return row["IndustryDomain"], "manual"
            
            # Get company products
            comp_products = products[products["CompanyMaster_FK_ID"] == row["Id"]]
            if comp_products.empty:
                return "", "none"
            
            # Combine all product text
            product_text = " ".join([
                str(comp_products["ProductName"].str.cat(sep=" ")),
                str(comp_products["Description"].str.cat(sep=" ")),
                str(comp_products["TechArea"].str.cat(sep=" ")),
                str(comp_products["Category"].str.cat(sep=" "))
            ]).lower()
            
            # Score each industry
            scores = {}
            for industry, keywords in industry_keywords.items():
                score = sum(1 for kw in keywords if kw in product_text)
                if score > 0:
                    scores[industry] = score
            
            if scores:
                best_industry = max(scores, key=scores.get)
                return best_industry, "inferred_from_products"
            
            return "", "none"
        
        # Apply inference
        enriched[["IndustryDomain_Inferred", "IndustryDomain_Source"]] = enriched.apply(
            infer_industry, axis=1, result_type="expand"
        )
        
        # Use inferred if original is empty
        enriched["IndustryDomain"] = enriched.apply(
            lambda r: r["IndustryDomain_Inferred"] if not r["IndustryDomain"].strip() else r["IndustryDomain"],
            axis=1
        )
    else:
        enriched["IndustryDomain_Source"] = "manual"
    
# --- PRODUCT AGGREGATIONS ---
    if not products.empty:
        prod_agg = products.groupby("CompanyMaster_FK_ID").agg({
            "ProductName": lambda x: " | ".join([str(v) for v in x[:5] if str(v).strip()]),  # Top 5
            "ProductId": "count",
            "Category": lambda x: " | ".join(sorted(set([str(v) for v in x if str(v).strip()]))),
            "TechArea": lambda x: " | ".join(sorted(set([str(v) for v in x if str(v).strip()]))),
            "DefencePlatform": lambda x: " | ".join(sorted(set([str(v) for v in x if str(v).strip()]))),
        }).reset_index().rename(columns={
            "CompanyMaster_FK_ID": "Id",
            "ProductName": "ProductNames_Sample",
            "ProductId": "ProductCount",
            "Category": "ProductCategories",
            "TechArea": "TechAreas",
            "DefencePlatform": "DefencePlatforms"
        })
        enriched = enriched.merge(prod_agg, on="Id", how="left")
    else:
        enriched["ProductCount"] = 0
        enriched["ProductNames_Sample"] = ""
        enriched["ProductCategories"] = ""
        enriched["TechAreas"] = ""
        enriched["DefencePlatforms"] = ""
    
# --- FACILITY AGGREGATIONS ---
    if not facilities.empty:
        fac_agg = facilities.groupby("CompanyMaster_FK_ID").agg({
            "FacilityType": "count",
            "Category": lambda x: " | ".join(sorted(set([str(v) for v in x if str(v).strip()]))),
        }).reset_index().rename(columns={
            "CompanyMaster_FK_ID": "Id",
            "FacilityType": "FacilityCount",
            "Category": "FacilityCategories"
        })
        enriched = enriched.merge(fac_agg, on="Id", how="left")
        
        # Count by type
        fac_by_type = facilities.groupby(["CompanyMaster_FK_ID", "FacilityType"]).size().unstack(fill_value=0).reset_index()
        fac_by_type = fac_by_type.rename(columns={"CompanyMaster_FK_ID": "Id"})
        for col in ["R&D", "TEST", "MFG"]:
            if col in fac_by_type.columns:
                enriched = enriched.merge(
                    fac_by_type[["Id", col]].rename(columns={col: f"{col}_FacilityCount"}),
                    on="Id", how="left"
                )
                enriched[f"{col}_FacilityCount"] = enriched[f"{col}_FacilityCount"].fillna(0).astype(int)
    else:
        enriched["FacilityCount"] = 0
        enriched["FacilityCategories"] = ""
    
# --- CERTIFICATION AGGREGATIONS ---
    if not certifications.empty:
        cert_agg = certifications.groupby("CompanyMaster_FK_ID").agg({
            "CertificationType": lambda x: " | ".join(sorted(set([str(v) for v in x if str(v).strip()]))),
            "Number": "count"
        }).reset_index().rename(columns={
            "CompanyMaster_FK_ID": "Id",
            "CertificationType": "CertificationTypes",
            "Number": "CertificationCount"
        })
        enriched = enriched.merge(cert_agg, on="Id", how="left")
    else:
        enriched["CertificationCount"] = 0
        enriched["CertificationTypes"] = ""
    
# --- TURNOVER AGGREGATIONS ---
    if not turnover.empty:
        # Get latest turnover
        turnover["TurnoverCr"] = pd.to_numeric(turnover["TurnoverCr"], errors="coerce")
        turnover["FY"] = pd.to_numeric(turnover["FY"], errors="coerce")
        
        latest_to = turnover.sort_values(["CompanyMaster_FK_ID", "FY"], na_position="last").drop_duplicates("CompanyMaster_FK_ID", keep="last")
        latest_to = latest_to.rename(columns={
            "CompanyMaster_FK_ID": "Id",
            "FY": "LatestTurnoverYear",
            "TurnoverCr": "LatestTurnoverCr"
        })
        enriched = enriched.merge(latest_to[["Id", "LatestTurnoverYear", "LatestTurnoverCr"]], on="Id", how="left")
    else:
        enriched["LatestTurnoverYear"] = ""
        enriched["LatestTurnoverCr"] = ""
    
# Fill NaN values
    enriched = enriched.fillna("")
    
# Write enriched view
    write_csv(enriched, OUT/"CompanyDetailEnriched.csv")
    print(f"✅ CompanyDetailEnriched.csv created with {len(enriched)} companies")
    
# Print some stats
    inferred_count = len(enriched[enriched.get("IndustryDomain_Source", "") == "inferred_from_products"])
    if inferred_count > 0:
        print(f"   ℹ️  Inferred industry domain for {inferred_count} companies from their products")

if __name__ == "__main__":
    main()

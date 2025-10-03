#!/usr/bin/env python3
"""
Validate classification keywords against actual CSV data
"""
import pandas as pd
from pathlib import Path

def main():
    print("=" * 80)
    print("VALIDATING CLASSIFICATION KEYWORDS AGAINST ACTUAL DATA")
    print("=" * 80)
    
    # Check Products
    print("\n### PRODUCTS ###")
    products = pd.read_csv('inputs/dbo.CompanyProducts.csv', encoding='latin-1')
    print(f"Total products: {len(products)}")
    print(f"\nColumns: {products.columns.tolist()}")
    print(f"\nSample product names (first 30):")
    for i, name in enumerate(products['ProductName'].dropna().head(30), 1):
        print(f"  {i}. {name}")
    
    # Check HSN codes
    if 'HSNCode' in products.columns:
        print(f"\nSample HSN codes:")
        hsn_samples = products['HSNCode'].dropna().head(20).tolist()
        print(f"  {hsn_samples}")
    
    # Check Facilities
    print("\n" + "=" * 80)
    print("### FACILITIES ###")
    facilities = pd.read_csv('inputs/dbo.CompanyTestFacility.csv', encoding='latin-1')
    print(f"Total test facilities: {len(facilities)}")
    print(f"\nColumns: {facilities.columns.tolist()}")
    
    if 'TestDetails' in facilities.columns:
        print(f"\nSample facility details:")
        for i, detail in enumerate(facilities['TestDetails'].dropna().head(20), 1):
            print(f"  {i}. {detail}")
    
    # Check if there are category masters
    test_cat_path = Path('inputs/dbo.TestFacilityCategoryMaster.csv')
    if test_cat_path.exists():
        test_cat = pd.read_csv(test_cat_path, encoding='latin-1')
        print(f"\nTest Facility Categories from master:")
        if 'TestFacilityCategoryName' in test_cat.columns:
            for cat in test_cat['TestFacilityCategoryName'].dropna().unique():
                print(f"  - {cat}")
        else:
            print(test_cat.head())
    
    # Check Certifications
    print("\n" + "=" * 80)
    print("### CERTIFICATIONS ###")
    cert = pd.read_csv('inputs/dbo.CompanyCertificationDetail.csv', encoding='latin-1')
    print(f"Total certifications: {len(cert)}")
    print(f"\nColumns: {cert.columns.tolist()}")
    
    # Check certification master
    cert_master_path = Path('inputs/dbo.CertificationTypeMaster.csv')
    if cert_master_path.exists():
        cert_master = pd.read_csv(cert_master_path, encoding='latin-1')
        print(f"\nCertification types from master:")
        print(f"Columns: {cert_master.columns.tolist()}")
        if 'CertificationName' in cert_master.columns:
            print("\nAll certification types:")
            for cert_name in cert_master['CertificationName'].dropna().unique():
                print(f"  - {cert_name}")
        else:
            print(cert_master.head(20))
    
    # Check R&D Facilities
    print("\n" + "=" * 80)
    print("### R&D FACILITIES ###")
    rd_path = Path('inputs/dbo.CompanyRDFacility.csv')
    if rd_path.exists():
        rd = pd.read_csv(rd_path, encoding='latin-1')
        print(f"Total R&D facilities: {len(rd)}")
        print(f"Columns: {rd.columns.tolist()}")
    else:
        print("No R&D facility file found")
    
    print("\n" + "=" * 80)
    print("VALIDATION COMPLETE")
    print("=" * 80)

if __name__ == '__main__':
    main()

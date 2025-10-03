#!/usr/bin/env python3
"""
Analyze all master tables and create comprehensive reference data
"""
import pandas as pd
from pathlib import Path

def main():
    print("=" * 100)
    print("COMPREHENSIVE MASTER TABLE ANALYSIS")
    print("=" * 100)
    
    # 1. Organization Type
    print("\n### ORGANIZATION TYPE ###")
    org = pd.read_csv('inputs/dbo.OrganisationTypeMaster.csv', encoding='latin-1')
    org_col = [c for c in org.columns if 'type' in c.lower()][0]
    print(f"Total types: {len(org)}")
    print("\nAll organization types:")
    for idx, val in org[org_col].items():
        if pd.notna(val):
            print(f"  {idx+1}. {val}")
    
    # 2. Scale/Company Size
    print("\n" + "=" * 100)
    print("### COMPANY SCALE ###")
    scale = pd.read_csv('inputs/dbo.ScaleMaster.csv', encoding='latin-1')
    scale_col = [c for c in scale.columns if 'scale' in c.lower()][0]
    print(f"Total scales: {len(scale)}")
    print("\nAll company scales:")
    for val in scale[scale_col].unique():
        if pd.notna(val):
            print(f"  - {val}")
    
    # 3. Industry Domain
    print("\n" + "=" * 100)
    print("### INDUSTRY DOMAIN ###")
    domain = pd.read_csv('inputs/dbo.IndustryDomainMaster.csv', encoding='latin-1')
    domain_col = [c for c in domain.columns if 'domain' in c.lower() or 'name' in c.lower()][0]
    print(f"Total domains: {len(domain)}")
    print("\nActive industry domains:")
    active_domains = domain[domain['IsActive'] == 1][domain_col].dropna().unique()
    for i, val in enumerate(active_domains, 1):
        print(f"  {i}. {val}")
    
    # 4. Industry Subdomain
    print("\n" + "=" * 100)
    print("### INDUSTRY SUBDOMAIN ###")
    subdomain_path = Path('inputs/dbo.IndustrySubdomainMaster.csv')
    if subdomain_path.exists():
        subdomain = pd.read_csv(subdomain_path, encoding='latin-1')
        print(f"Total subdomains: {len(subdomain)}")
        subdomain_col = [c for c in subdomain.columns if 'subdomain' in c.lower() or 'name' in c.lower()]
        if subdomain_col:
            print("\nSample subdomains (first 30):")
            for i, val in enumerate(subdomain[subdomain_col[0]].dropna().head(30), 1):
                print(f"  {i}. {val}")
    else:
        print("File not found")
    
    # 5. Core Expertise
    print("\n" + "=" * 100)
    print("### CORE EXPERTISE ###")
    expertise = pd.read_csv('inputs/dbo.CompanyCoreExpertiseMaster.csv', encoding='latin-1')
    expertise_col = [c for c in expertise.columns if 'expert' in c.lower() or 'name' in c.lower()][0]
    print(f"Total expertise areas: {len(expertise)}")
    print("\nTop expertise areas:")
    active_expertise = expertise[expertise['IsActive'] == 1][expertise_col].dropna().head(50)
    for i, val in enumerate(active_expertise, 1):
        print(f"  {i}. {val}")
    
    # 6. Turnover
    print("\n" + "=" * 100)
    print("### COMPANY TURNOVER ###")
    turnover_path = Path('inputs/dbo.CompanyTurnOver.csv')
    if turnover_path.exists():
        turnover = pd.read_csv(turnover_path, encoding='latin-1')
        print(f"Total records: {len(turnover)}")
        print(f"Columns: {turnover.columns.tolist()}")
        print("\nSample turnover data:")
        print(turnover.head(10))
    else:
        print("Turnover file not found")
    
    # 7. Product Type Master
    print("\n" + "=" * 100)
    print("### PRODUCT TYPE ###")
    prod_type_path = Path('inputs/dbo.ProductTypeMaster.csv')
    if prod_type_path.exists():
        prod_type = pd.read_csv(prod_type_path, encoding='latin-1')
        print(f"Total product types: {len(prod_type)}")
        type_col = [c for c in prod_type.columns if 'type' in c.lower() or 'name' in c.lower()]
        if type_col:
            print("\nAll product types:")
            for val in prod_type[type_col[0]].dropna().unique():
                print(f"  - {val}")
    else:
        print("Product type master not found")
    
    # 8. Defence Platform Master
    print("\n" + "=" * 100)
    print("### DEFENCE PLATFORM ###")
    platform_path = Path('inputs/dbo.DefencePlatformMaster.csv')
    if platform_path.exists():
        platform = pd.read_csv(platform_path, encoding='latin-1')
        print(f"Total platforms: {len(platform)}")
        plat_col = [c for c in platform.columns if 'platform' in c.lower() or 'name' in c.lower()]
        if plat_col:
            print("\nDefence platforms:")
            for val in platform[plat_col[0]].dropna().unique():
                print(f"  - {val}")
    else:
        print("Defence platform master not found")
    
    print("\n" + "=" * 100)
    print("ANALYSIS COMPLETE")
    print("=" * 100)

if __name__ == '__main__':
    main()

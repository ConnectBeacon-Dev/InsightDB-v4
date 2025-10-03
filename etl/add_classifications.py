#!/usr/bin/env python3
"""
Helper module for adding company classifications
"""
import pandas as pd
from pathlib import Path
from industry_reference_data import get_industry_from_hsn, check_known_company

def add_company_classifications(df: pd.DataFrame, inputs_dir: str = 'inputs') -> pd.DataFrame:
    """
    Add pre-computed classification columns for fast exact-match filtering.
    These boolean/categorical fields enable instant filtering without semantic search.
    Also infers IndustryDomain from company names, products, facilities, and available data.
    """
    
    # 0. Infer Industry Domain from comprehensive data analysis
    df = _infer_industry_domain(df, inputs_dir)
    
    # 1. Government Company Classification
    if 'CompanySubCategory' in df.columns:
        df['is_union_government'] = df['CompanySubCategory'].str.match(
            r'^Union\s+government\s+company', case=False, na=False
        )
        df['is_state_government'] = df['CompanySubCategory'].str.match(
            r'^State\s+government\s+company', case=False, na=False
        )
        df['is_government_company'] = df['is_union_government'] | df['is_state_government']
        df['is_private_company'] = df['CompanySubCategory'].str.contains(
            'Non-government', case=False, na=False
        )
    else:
        df['is_union_government'] = False
        df['is_state_government'] = False
        df['is_government_company'] = False
        df['is_private_company'] = False
    
    # 2. Company Status Classification
    if 'CompanyStatus' in df.columns:
        df['is_active_company'] = df['CompanyStatus'].str.contains(
            'active', case=False, na=False
        )
    else:
        df['is_active_company'] = False
    
    # 3. MSME Classification (multiple sources)
    msme_mask = pd.Series(False, index=df.index)
    if 'Scale' in df.columns:
        msme_mask |= df['Scale'].str.contains(
            'micro|small|medium|msme', case=False, na=False, regex=True
        )
    df['is_msme'] = msme_mask
    
    # 4. Listed Company Classification
    if 'ListingStatus' in df.columns:
        df['is_listed_company'] = df['ListingStatus'].str.contains(
            'listed', case=False, na=False
        )
    else:
        df['is_listed_company'] = False
    
    # 5. Defence/Aerospace Classification
    if 'IndustryDomain' in df.columns:
        df['is_defence_company'] = df['IndustryDomain'].str.contains(
            'defence|defense|aerospace|military', case=False, na=False, regex=True
        )
    else:
        df['is_defence_company'] = False
    
    # 6. Company Size Category (derived from multiple fields)
    df['company_size_category'] = 'Unknown'
    if 'Scale' in df.columns:
        df.loc[df['Scale'].str.contains('micro', case=False, na=False), 'company_size_category'] = 'Micro'
        df.loc[df['Scale'].str.contains('small', case=False, na=False), 'company_size_category'] = 'Small'
        df.loc[df['Scale'].str.contains('medium', case=False, na=False), 'company_size_category'] = 'Medium'
        df.loc[df['Scale'].str.contains('large', case=False, na=False), 'company_size_category'] = 'Large'
    
    # 7. Company Type Normalized
    df['company_type_normalized'] = 'Unknown'
    if 'CompanySubCategory' in df.columns:
        df.loc[df['is_union_government'] == True, 'company_type_normalized'] = 'Union Government / PSU'
        df.loc[df['is_state_government'] == True, 'company_type_normalized'] = 'State Government / PSU'
        df.loc[df['is_private_company'] == True, 'company_type_normalized'] = 'Private Company'
    
    return df


def _infer_industry_domain(df: pd.DataFrame, inputs_dir: str = 'inputs') -> pd.DataFrame:
    """
    Infer IndustryDomain from comprehensive data analysis including:
    - Company names
    - Product names and descriptions
    - Facility types and equipment
    - Address information
    
    This data-driven approach analyzes actual products and facilities for accurate classification.
    """
    
    # Initialize IndustryDomain - replace any NaN/null with empty string
    if 'IndustryDomain' not in df.columns:
        df['IndustryDomain'] = ''
    else:
        df['IndustryDomain'] = df['IndustryDomain'].fillna('').astype(str)
    
    # Enhanced industry keywords with comprehensive patterns
    industry_patterns = {
        'Pharmaceuticals': [
            r'\b(pharma|pharmaceutical|drug|medicine|healthcare|biotech|medical|therapeutic|diagnostic|clinical)\b',
            r'\b(tablet|capsule|injection|syrup|antibiotic|vaccine|surgical)\b'
        ],
        'Electrical & Electronics': [
            r'\b(electrical|electronic|electronics|power|energy|solar|battery|transformer|switchgear)\b',
            r'\b(cable|wire|conductor|circuit|LED|panel|meter|relay|contactor|busbar)\b',
            r'\b(inverter|UPS|generator|alternator|motor|dynamo|capacitor|resistor)\b',
            r'\b(semiconductor|diode|transistor|PCB|microcontroller|sensor|actuator)\b',
            r'\b(voltage|current|ampere|watt|kilowatt|substation|grid)\b'
        ],
        'Automotive': [
            r'\b(auto|automotive|vehicle|car|truck|motor|mobility|automobile)\b',
            r'\b(brake|clutch|gear|axle|suspension|steering|engine component|piston)\b'
        ],
        'Aerospace & Defence': [
            r'\b(aerospace|defence|defense|military|aviation|aircraft|missile|radar|naval|submarine)\b',
            r'\b(ammunition|weapon|armament|combat|fighter|helicopter|warship)\b'
        ],
        'Textiles': [
            r'\b(textile|fabric|garment|apparel|clothing|fiber|cotton|polyester|yarn|weaving|spinning)\b'
        ],
        'Steel & Metals': [
            r'\b(steel|metal|iron|aluminium|aluminum|copper|brass|zinc|alloy|metallurg|foundry|casting)\b',
            r'\b(wire rope|rod|bar|sheet|plate|coil|ingot|billet|forging)\b'
        ],
        'Chemicals': [
            r'\b(chemical|polymer|resin|coating|paint|adhesive|solvent|acid|alkali|fertilizer)\b'
        ],
        'Food & Beverages': [
            r'\b(food|beverage|dairy|egg|meat|agri|agriculture|grain|flour|oil|spice|bakery)\b'
        ],
        'IT & Software': [
            r'\b(software|technology|IT|information technology|digital|cyber|data|cloud|AI|computer)\b'
        ],
        'Construction & Engineering': [
            r'\b(construction|engineering|infrastructure|building|cement|concrete|civil|structural)\b'
        ],
        'Machinery & Equipment': [
            r'\b(machinery|machine|equipment|tool|compressor|pump|valve|bearing|conveyor)\b'
        ],
        'Plastics': [
            r'\b(plastic|polymer|PVC|polyethylene|polypropylene|moulding|extrusion|injection)\b'
        ],
    }
    
    # Step 0: Check known major companies (highest confidence)
    print("     🔍 Checking known major companies...")
    if 'CompanyName' in df.columns:
        for idx, row in df[df['IndustryDomain'].isin(['', 'Other'])].iterrows():
            known_industry = check_known_company(row['CompanyName'])
            if known_industry:
                df.at[idx, 'IndustryDomain'] = known_industry
    
    # Step 0.5: HSN Code-based classification (very high confidence)
    print("     🔍 Analyzing HSN codes from products for industry classification...")
    try:
        products_path = Path(inputs_dir) / 'dbo.CompanyProducts.csv'
        if products_path.exists():
            products = pd.read_csv(products_path, encoding='latin-1')
            
            if 'CompanyMaster_FK_ID' in products.columns and 'HSNCode' in products.columns:
                # Convert IDs to same type (string) for reliable matching
                products['CompanyMaster_FK_ID'] = products['CompanyMaster_FK_ID'].astype(str)
                df['Id'] = df['Id'].astype(str)
                
                # Get HSN-based industry for each company
                hsn_classifications = {}
                for _, row in products.iterrows():
                    company_id = str(row['CompanyMaster_FK_ID']).strip()
                    hsn_code = str(row['HSNCode']).strip() if pd.notna(row['HSNCode']) else ''
                    
                    if not company_id or company_id == 'nan':
                        continue
                        
                    industry = get_industry_from_hsn(hsn_code)
                    if industry:
                        if company_id not in hsn_classifications:
                            hsn_classifications[company_id] = {}
                        hsn_classifications[company_id][industry] = hsn_classifications[company_id].get(industry, 0) + 1
                
                # Apply HSN-based classification (pick industry with most HSN matches)
                hsn_count = 0
                for company_id, industries in hsn_classifications.items():
                    if industries:
                        # Pick industry with most product HSN matches
                        best_industry = max(industries.items(), key=lambda x: x[1])[0]
                        mask = (df['Id'] == company_id) & (df['IndustryDomain'].isin(['', 'Other']))
                        matched = mask.sum()
                        if matched > 0:
                            df.loc[mask, 'IndustryDomain'] = best_industry
                            hsn_count += 1
                
                if hsn_count > 0:
                    print(f"     ✅ Classified {hsn_count} companies using HSN codes")
                else:
                    print(f"     ℹ️  HSN codes analyzed but no new classifications (companies may already be classified)")
    except Exception as e:
        print(f"     ⚠️  Could not analyze HSN codes: {e}")
    
    print("     🔍 Analyzing company names for industry classification...")
    # Step 1: Check company name
    if 'CompanyName' in df.columns:
        for industry, patterns in industry_patterns.items():
            for pattern in patterns:
                mask = (df['IndustryDomain'].isin(['', 'Other'])) & df['CompanyName'].str.contains(pattern, case=False, na=False, regex=True)
                count = mask.sum()
                if count > 0:
                    df.loc[mask, 'IndustryDomain'] = industry
    
    print("     🔍 Analyzing products data for industry classification...")
    # Step 2: Load and analyze Products data
    try:
        products_path = Path(inputs_dir) / 'dbo.CompanyProducts.csv'
        if products_path.exists():
            products = pd.read_csv(products_path, encoding='latin-1')
            
            # Group products by company
            if 'CompanyMaster_FK_ID' in products.columns and 'ProductName' in products.columns:
                # Convert IDs to same type for reliable matching
                products['CompanyMaster_FK_ID'] = products['CompanyMaster_FK_ID'].astype(str)
                
                # Aggregate product names per company
                product_summary = products.groupby('CompanyMaster_FK_ID')['ProductName'].apply(
                    lambda x: ' '.join(x.dropna().astype(str))
                ).reset_index()
                product_summary.columns = ['Id', 'ProductText']
                
                # Ensure Id is string for merge
                product_summary['Id'] = product_summary['Id'].astype(str)
                
                # Merge with main dataframe
                df = df.merge(product_summary, on='Id', how='left')
                
                # Check product text for industry keywords
                if 'ProductText' in df.columns:
                    for industry, patterns in industry_patterns.items():
                        for pattern in patterns:
                            mask = (df['IndustryDomain'].isin(['', 'Other'])) & df['ProductText'].str.contains(pattern, case=False, na=False, regex=True)
                            count = mask.sum()
                            if count > 0:
                                df.loc[mask, 'IndustryDomain'] = industry
                    
                    # Drop temporary column
                    df.drop('ProductText', axis=1, inplace=True)
                    print("     ✅ Products data analyzed successfully")
    except Exception as e:
        print(f"     ⚠️  Could not load products data: {e}")
    
    print("     🔍 Analyzing facilities data for industry classification...")
    # Step 3: Load and analyze Facilities data
    try:
        facilities_path = Path(inputs_dir) / 'dbo.CompanyTestFacility.csv'
        if facilities_path.exists():
            facilities = pd.read_csv(facilities_path, encoding='latin-1')
            
            if 'CompanyMaster_FK_ID' in facilities.columns:
                # Convert IDs to same type for reliable matching
                facilities['CompanyMaster_FK_ID'] = facilities['CompanyMaster_FK_ID'].astype(str)
                
                # Get facility info columns
                facility_cols = [c for c in facilities.columns if c in ['TestFacilityName', 'TestFacilityDesc', 'Equipment']]
                if facility_cols:
                    facility_text = facilities[['CompanyMaster_FK_ID'] + facility_cols].copy()
                    facility_text['FacilityText'] = facility_text[facility_cols].apply(
                        lambda x: ' '.join(x.dropna().astype(str)), axis=1
                    )
                    
                    # Aggregate by company
                    facility_summary = facility_text.groupby('CompanyMaster_FK_ID')['FacilityText'].apply(
                        lambda x: ' '.join(x)
                    ).reset_index()
                    facility_summary.columns = ['Id', 'FacilityText']
                    
                    # Ensure Id is string for merge
                    facility_summary['Id'] = facility_summary['Id'].astype(str)
                    
                    # Merge with main dataframe
                    df = df.merge(facility_summary, on='Id', how='left')
                    
                    # Check facility text for industry keywords
                    if 'FacilityText' in df.columns:
                        for industry, patterns in industry_patterns.items():
                            for pattern in patterns:
                                mask = (df['IndustryDomain'].isin(['', 'Other'])) & df['FacilityText'].str.contains(pattern, case=False, na=False, regex=True)
                                count = mask.sum()
                                if count > 0:
                                    df.loc[mask, 'IndustryDomain'] = industry
                        
                        # Drop temporary column
                        df.drop('FacilityText', axis=1, inplace=True)
                        print("     ✅ Facilities data analyzed successfully")
    except Exception as e:
        print(f"     ⚠️  Could not load facilities data: {e}")
    
    # Step 4: Check Address for additional context
    if 'Address' in df.columns:
        tech_pattern = r'(tech park|technology|IT park|software|cyber)'
        industrial_pattern = r'(industrial area|industrial estate|MIDC|industrial zone)'
        
        mask_tech = (df['IndustryDomain'].isin(['', 'Other'])) & df['Address'].str.contains(tech_pattern, case=False, na=False, regex=True)
        df.loc[mask_tech, 'IndustryDomain'] = 'IT & Software'
        
        mask_industrial = (df['IndustryDomain'].isin(['', 'Other'])) & df['Address'].str.contains(industrial_pattern, case=False, na=False, regex=True)
        df.loc[mask_industrial, 'IndustryDomain'] = 'Manufacturing'
    
    # Set a default for remaining companies
    df.loc[df['IndustryDomain'].isin(['', 'nan', 'NaN']), 'IndustryDomain'] = 'Other'
    
    # Step 5: LLM-based classification for remaining "Other" companies
    print("     🤖 Using LLM classifier for remaining companies...")
    other_mask = df['IndustryDomain'] == 'Other'
    other_count = other_mask.sum()
    
    if other_count > 0:
        try:
            from llm_classifier import get_classifier
            
            classifier = get_classifier()
            
            # Prepare companies for batch classification
            companies_to_classify = []
            other_indices = []
            
            for idx in df[other_mask].index:
                row = df.loc[idx]
                companies_to_classify.append({
                    'name': row.get('CompanyName', ''),
                    'address': row.get('Address', ''),
                    'certifications': [],  # Could load from certifications file if needed
                    'context': ''
                })
                other_indices.append(idx)
            
            # Classify in batches
            print(f"     🔄 Classifying {len(companies_to_classify)} companies using LLM...")
            classifications = classifier.classify_batch(companies_to_classify, confidence_threshold=0.35)
            
            # Apply results
            llm_count = 0
            for idx, classification in zip(other_indices, classifications):
                if classification:
                    df.at[idx, 'IndustryDomain'] = classification
                    llm_count += 1
            
            if llm_count > 0:
                print(f"     ✅ LLM classified {llm_count} additional companies")
            else:
                print(f"     ℹ️  LLM unable to confidently classify remaining companies")
        
        except Exception as e:
            print(f"     ⚠️  LLM classification failed: {e}")
            print(f"     ℹ️  Continuing with rule-based classifications only")
    
    return df


def write_company_classifications(out_dir, company_df: pd.DataFrame) -> None:
    """
    Write a separate classifications file for fast lookup and filtering.
    This file contains only Id + boolean/categorical classification columns.
    """
    from pathlib import Path
    
    out_dir = Path(out_dir)
    
    if company_df.empty or 'Id' not in company_df.columns:
        return
    
    classification_cols = [
        'Id',
        'is_union_government',
        'is_state_government', 
        'is_government_company',
        'is_private_company',
        'is_msme',
        'is_listed_company',
        'is_active_company',
        'is_defence_company',
        'company_size_category',
        'company_type_normalized'
    ]
    
    existing_cols = [c for c in classification_cols if c in company_df.columns]
    
    if len(existing_cols) > 1:  # More than just 'Id'
        classifications = company_df[existing_cols].copy()
        classifications.to_csv(out_dir / "CompanyClassifications.csv", index=False)
        print(f"  -> {out_dir/'CompanyClassifications.csv'} ({len(classifications)} rows)")
        
        # Also print statistics
        if 'is_government_company' in classifications.columns:
            govt_count = classifications['is_government_company'].sum()
            print(f"     ℹ️  Found {govt_count} government companies")
        if 'is_msme' in classifications.columns:
            msme_count = classifications['is_msme'].sum()
            print(f"     ℹ️  Found {msme_count} MSME companies")

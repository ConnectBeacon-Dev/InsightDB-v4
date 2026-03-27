#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os

# Fix encoding for Windows console (must be before any other imports)
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    os.environ['PYTHONIOENCODING'] = 'utf-8'

"""
Comprehensive Test Suite with Result Verification
Tests all requested query types and verifies results against input data
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.full_engine_query import EnhancedQueryEngine
import pandas as pd
import os
import warnings
import time
import json
from datetime import datetime

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')
os.environ['LLAMA_LOG_LEVEL'] = '0'

class TestResultVerifier:
    """Verify test results against input data"""
    
    def __init__(self, inputs_dir="inputs"):
        self.inputs_dir = Path(inputs_dir)
        self.load_data()
    
    def load_data(self):
        """Load all necessary input data for verification"""
        print("Loading input data for verification...")
        
        # Load master tables
        self.company_master = pd.read_csv(self.inputs_dir / "dbo.CompanyMaster.csv", encoding='utf-8')
        self.certifications = pd.read_csv(self.inputs_dir / "dbo.CompanyCertificationDetail.csv", encoding='utf-8')
        self.cert_types = pd.read_csv(self.inputs_dir / "dbo.CertificationTypeMaster.csv", encoding='utf-8')
        self.products = pd.read_csv(self.inputs_dir / "dbo.CompanyProducts.csv", encoding='utf-8')
        self.product_types = pd.read_csv(self.inputs_dir / "dbo.ProductTypeMaster.csv", encoding='utf-8')
        self.test_facilities = pd.read_csv(self.inputs_dir / "dbo.CompanyTestFacility.csv", encoding='utf-8')
        self.test_categories = pd.read_csv(self.inputs_dir / "dbo.TestFacilityCategoryMaster.csv", encoding='utf-8')
        self.test_subcategories = pd.read_csv(self.inputs_dir / "dbo.TestFacilitySubCategoryMaster.csv", encoding='utf-8')
        self.industry_domains = pd.read_csv(self.inputs_dir / "dbo.IndustryDomainMaster.csv", encoding='utf-8')
        self.scale_master = pd.read_csv(self.inputs_dir / "dbo.ScaleMaster.csv", encoding='utf-8')
        self.org_types = pd.read_csv(self.inputs_dir / "dbo.OrganisationTypeMaster.csv", encoding='utf-8')
        
        print(f"✓ Loaded {len(self.company_master)} companies")
        print(f"✓ Loaded {len(self.certifications)} certifications")
        print(f"✓ Loaded {len(self.products)} products")
        print(f"✓ Loaded {len(self.test_facilities)} test facilities")
    
    def verify_defence_startups(self, results):
        """Verify defence startup results"""
        print("\n🔍 Verifying Defence Startups...")
        
        # Get startup org type ID
        startup_types = self.org_types[self.org_types['OrganisationTypeName'].str.contains('Startup', case=False, na=False)]
        if startup_types.empty:
            print("⚠ Warning: No startup organization type found in master data")
            return False
        
        startup_type_ids = startup_types['OrganisationTypeID'].tolist()
        
        # Get defence domain IDs
        defence_domains = self.industry_domains[
            self.industry_domains['IndustryDomainName'].str.contains('Defence|Defense|Aerospace', case=False, na=False, regex=True)
        ]
        defence_domain_ids = defence_domains['IndustryDomainID'].tolist()
        
        # Expected defence startups
        expected = self.company_master[
            (self.company_master['OrganisationTypeID'].isin(startup_type_ids)) &
            (self.company_master['IndustryDomainID'].isin(defence_domain_ids))
        ]
        
        print(f"Expected defence startups in data: {len(expected)}")
        print(f"Results returned: {len(results)}")
        
        # Check if results are subset of expected
        if not results.empty and 'CompanyID' in results.columns:
            result_ids = set(results['CompanyID'].tolist())
            expected_ids = set(expected['CompanyID'].tolist())
            correct_matches = result_ids.intersection(expected_ids)
            
            accuracy = len(correct_matches) / len(result_ids) * 100 if result_ids else 0
            print(f"✓ Accuracy: {accuracy:.1f}% ({len(correct_matches)}/{len(result_ids)} correct)")
            
            return accuracy > 70  # 70% threshold
        
        return False
    
    def verify_msme(self, results):
        """Verify MSME results"""
        print("\n🔍 Verifying MSME Companies...")
        
        # Get MSME scale IDs
        msme_scales = self.scale_master[
            self.scale_master['ScaleName'].str.contains('MSME|Micro|Small|Medium', case=False, na=False, regex=True)
        ]
        msme_scale_ids = msme_scales['ScaleID'].tolist()
        
        # Expected MSME companies
        expected = self.company_master[self.company_master['ScaleID'].isin(msme_scale_ids)]
        
        print(f"Expected MSME companies in data: {len(expected)}")
        print(f"Results returned: {len(results)}")
        
        if not results.empty and 'CompanyID' in results.columns:
            result_ids = set(results['CompanyID'].tolist())
            expected_ids = set(expected['CompanyID'].tolist())
            correct_matches = result_ids.intersection(expected_ids)
            
            accuracy = len(correct_matches) / len(result_ids) * 100 if result_ids else 0
            print(f"✓ Accuracy: {accuracy:.1f}% ({len(correct_matches)}/{len(result_ids)} correct)")
            
            return accuracy > 70
        
        return False
    
    def verify_location(self, results, location):
        """Verify location-based results"""
        print(f"\n🔍 Verifying Companies in {location}...")
        
        # Expected companies in location
        expected = self.company_master[
            self.company_master['City'].str.contains(location, case=False, na=False) |
            self.company_master['State'].str.contains(location, case=False, na=False)
        ]
        
        print(f"Expected companies in {location}: {len(expected)}")
        print(f"Results returned: {len(results)}")
        
        if not results.empty:
            # Check if results match location
            location_matches = results[
                results['City'].str.contains(location, case=False, na=False) |
                results['State'].str.contains(location, case=False, na=False)
            ]
            
            accuracy = len(location_matches) / len(results) * 100 if len(results) > 0 else 0
            print(f"✓ Accuracy: {accuracy:.1f}% ({len(location_matches)}/{len(results)} correct)")
            
            return accuracy > 80
        
        return False
    
    def verify_certification(self, results, cert_name):
        """Verify certification results"""
        print(f"\n🔍 Verifying Companies with {cert_name}...")
        
        # Get certification type ID
        cert_type = self.cert_types[
            self.cert_types['CertificationTypeName'].str.contains(cert_name, case=False, na=False)
        ]
        
        if cert_type.empty:
            print(f"⚠ Warning: Certification type '{cert_name}' not found in master data")
            return False
        
        cert_type_id = cert_type['CertificationTypeID'].iloc[0]
        
        # Get companies with this certification
        companies_with_cert = self.certifications[
            self.certifications['CertificationTypeID'] == cert_type_id
        ]['CompanyID'].unique()
        
        print(f"Expected companies with {cert_name}: {len(companies_with_cert)}")
        print(f"Results returned: {len(results)}")
        
        if not results.empty and 'CompanyID' in results.columns:
            result_ids = set(results['CompanyID'].tolist())
            expected_ids = set(companies_with_cert)
            correct_matches = result_ids.intersection(expected_ids)
            
            accuracy = len(correct_matches) / len(result_ids) * 100 if result_ids else 0
            print(f"✓ Accuracy: {accuracy:.1f}% ({len(correct_matches)}/{len(result_ids)} correct)")
            
            return accuracy > 70
        
        return False
    
    def verify_company_attribute(self, results, company_name, attribute):
        """Verify company-specific attribute query"""
        print(f"\n🔍 Verifying {attribute} for {company_name}...")
        
        # Find company in master data
        company = self.company_master[
            self.company_master['CompanyName'].str.contains(company_name, case=False, na=False)
        ]
        
        if company.empty:
            print(f"⚠ Warning: Company '{company_name}' not found in master data")
            return False
        
        print(f"Found company in master data: {company['CompanyName'].iloc[0]}")
        
        if not results.empty:
            # Check if top result is the correct company
            if 'CompanyName' in results.columns:
                top_result = results.iloc[0]['CompanyName']
                is_correct = company_name.lower() in top_result.lower()
                
                if is_correct:
                    print(f"✓ Correct company found: {top_result}")
                    
                    # Verify attribute is present
                    if attribute in results.columns and pd.notna(results.iloc[0][attribute]):
                        print(f"✓ {attribute} present: {results.iloc[0][attribute]}")
                        return True
                    else:
                        print(f"⚠ {attribute} not found or empty in results")
                        return False
                else:
                    print(f"✗ Wrong company returned: {top_result}")
                    return False
        
        return False
    
    def verify_product_query(self, results, product_criteria):
        """Verify product-based query results"""
        print(f"\n🔍 Verifying Product Query: {product_criteria}...")
        
        print(f"Results returned: {len(results)}")
        
        # Basic validation - check if results have product-related data
        if not results.empty:
            print(f"✓ Found {len(results)} results")
            return True
        else:
            print("⚠ No results found")
            return False
    
    def verify_industry_query(self, results, industry_keywords):
        """Verify industry-specific query results"""
        print(f"\n🔍 Verifying Industry Query: {industry_keywords}...")
        
        # Find relevant industry domains
        relevant_domains = self.industry_domains[
            self.industry_domains['IndustryDomainName'].str.contains(
                '|'.join(industry_keywords), case=False, na=False, regex=True
            )
        ]
        
        print(f"Relevant industry domains found: {len(relevant_domains)}")
        print(f"Results returned: {len(results)}")
        
        if not results.empty and 'IndustryDomain' in results.columns:
            # Check if results match industry
            matching_results = results[
                results['IndustryDomain'].str.contains(
                    '|'.join(industry_keywords), case=False, na=False, regex=True
                )
            ]
            
            accuracy = len(matching_results) / len(results) * 100 if len(results) > 0 else 0
            print(f"✓ Accuracy: {accuracy:.1f}% ({len(matching_results)}/{len(results)} match industry)")
            
            return accuracy > 50  # Lower threshold for industry queries
        
        return False
    
    def verify_test_facility(self, results, facility_type):
        """Verify test facility query results"""
        print(f"\n🔍 Verifying Test Facility Query: {facility_type}...")
        
        # Find relevant test facility categories
        relevant_categories = self.test_categories[
            self.test_categories['TestFacilityCategoryName'].str.contains(
                facility_type, case=False, na=False
            )
        ]
        
        if relevant_categories.empty:
            # Try subcategories
            relevant_subcategories = self.test_subcategories[
                self.test_subcategories['TestFacilitySubCategoryName'].str.contains(
                    facility_type, case=False, na=False
                )
            ]
            
            if not relevant_subcategories.empty:
                category_ids = relevant_subcategories['TestFacilityCategoryID'].unique()
                relevant_categories = self.test_categories[
                    self.test_categories['TestFacilityCategoryID'].isin(category_ids)
                ]
        
        if not relevant_categories.empty:
            category_ids = relevant_categories['TestFacilityCategoryID'].unique()
            companies_with_facility = self.test_facilities[
                self.test_facilities['TestFacilityCategoryID'].isin(category_ids)
            ]['CompanyID'].unique()
            
            print(f"Expected companies with {facility_type} facility: {len(companies_with_facility)}")
            print(f"Results returned: {len(results)}")
            
            if not results.empty and 'CompanyID' in results.columns:
                result_ids = set(results['CompanyID'].tolist())
                expected_ids = set(companies_with_facility)
                correct_matches = result_ids.intersection(expected_ids)
                
                accuracy = len(correct_matches) / len(result_ids) * 100 if result_ids else 0
                print(f"✓ Accuracy: {accuracy:.1f}% ({len(correct_matches)}/{len(result_ids)} correct)")
                
                return accuracy > 60
        else:
            print(f"⚠ No test facility category found for '{facility_type}'")
        
        return False


class TestCase:
    """Represents a single test case"""
    
    def __init__(self, name, query, category, verification_func=None, verification_args=None, top_k=20):
        self.name = name
        self.query = query
        self.category = category
        self.verification_func = verification_func
        self.verification_args = verification_args or {}
        self.top_k = top_k
        self.result = None
        self.passed = None
        self.execution_time = None
        self.error = None


def run_test_case(engine, verifier, test_case):
    """Run a single test case with verification"""
    print(f"\n{'='*80}")
    print(f" {test_case.name}")
    print(f"{'='*80}")
    print(f"Query: {test_case.query}")
    print(f"Category: {test_case.category}\n")
    
    try:
        # Run the query with timing
        print("⏳ Processing query...")
        start_time = time.time()
        response = engine.natural_language_query(test_case.query, top_k=test_case.top_k)
        test_case.execution_time = time.time() - start_time
        
        # Display LLM answer
        print(f"\n{'='*80}")
        print(f" LLM ANSWER (⏱ {test_case.execution_time:.2f}s)")
        print(f"{'='*80}")
        print(response["answer"])
        
        # Display results summary
        results = response["results"]
        test_case.result = results
        
        if not results.empty:
            print(f"\n{'='*80}")
            print(f" TOP {min(10, len(results))} RESULTS")
            print(f"{'='*80}\n")
            
            # Display results
            for idx, (_, row) in enumerate(results.head(10).iterrows(), 1):
                name = row.get("CompanyName", "N/A")
                state = row.get("State", "N/A")
                city = row.get("City", "N/A")
                
                print(f"{idx:2d}. {name}")
                print(f"     Location: {city}, {state}")
                
                # Show relevant attributes based on query type
                if 'Address' in row and pd.notna(row['Address']):
                    print(f"     Address: {row['Address'][:100]}...")
                if 'PAN' in row and pd.notna(row['PAN']):
                    print(f"     PAN: {row['PAN']}")
                if 'ContactNo' in row and pd.notna(row['ContactNo']):
                    print(f"     Contact: {row['ContactNo']}")
                
                print()
            
            print(f" Total found: {len(results)} results\n")
        else:
            print("\n ⚠ No results found.\n")
        
        # Run verification if provided
        if test_case.verification_func:
            test_case.passed = test_case.verification_func(results, **test_case.verification_args)
        else:
            # Default verification - just check if results exist
            test_case.passed = not results.empty
        
        if test_case.passed:
            print("\n✅ TEST PASSED")
        else:
            print("\n❌ TEST FAILED")
        
    except Exception as e:
        test_case.error = str(e)
        test_case.passed = False
        print(f"\n❌ TEST ERROR: {e}")
    
    return test_case


def main():
    print("="*80)
    print("COMPREHENSIVE TEST SUITE WITH RESULT VERIFICATION")
    print("="*80)
    
    # Initialize engine
    LLM_PATH = r"models\Qwen2.5-3B-Instruct-Q8_0.gguf"
    print(f"\nInitializing query engine...")
    print(f"LLM Path: {LLM_PATH}")
    
    # Go to parent directory for correct paths
    parent_dir = Path(__file__).resolve().parent.parent
    os.chdir(parent_dir)
    
    engine = EnhancedQueryEngine(
        views_dir="views", 
        model_name="models/all-MiniLM-L6-v2",
        llm_model_path=LLM_PATH
    )
    
    # Build semantic index
    print("Building/checking semantic index...")
    engine.build_semantic_index(force=False)
    
    # Initialize verifier
    verifier = TestResultVerifier(inputs_dir="inputs")
    
    # Define all test cases
    test_cases = [
        # Category 1: Filter Queries
        TestCase(
            "Test 1: Defence Startups",
            "List all defence startups",
            "Filter Query",
            verifier.verify_defence_startups,
            {},
            top_k=30
        ),
        TestCase(
            "Test 2: MSME Companies",
            "List of MSME in India",
            "Filter Query",
            verifier.verify_msme,
            {},
            top_k=30
        ),
        TestCase(
            "Test 3: Companies in Bhopal",
            "Companies based in Bhopal",
            "Location Query",
            verifier.verify_location,
            {"location": "Bhopal"},
            top_k=30
        ),
        
        # Category 2: Certification Queries
        TestCase(
            "Test 4: ISO 9001 Certification",
            "List of companies having ISO 9001 certification",
            "Certification Query",
            verifier.verify_certification,
            {"cert_name": "ISO 9001"},
            top_k=30
        ),
        
        # Category 3: Company Attribute Queries
        TestCase(
            "Test 5: Address of FLONEX",
            "Address of FLONEX OIL TECHNOLOGIES PRIVATE LIMITED",
            "Company Attribute Query",
            verifier.verify_company_attribute,
            {"company_name": "FLONEX OIL TECHNOLOGIES", "attribute": "Address"},
            top_k=5
        ),
        TestCase(
            "Test 6: PAN of K G DENIM",
            "Pan of K G DENIM Limited",
            "Company Attribute Query",
            verifier.verify_company_attribute,
            {"company_name": "K G DENIM", "attribute": "PAN"},
            top_k=5
        ),
        TestCase(
            "Test 7: Contact Details of MADHYA BHARAT AGRO",
            "Contact Details of MADHYA BHARAT AGRO PRODUCTS LIMITED",
            "Company Attribute Query",
            verifier.verify_company_attribute,
            {"company_name": "MADHYA BHARAT AGRO", "attribute": "ContactNo"},
            top_k=5
        ),
        TestCase(
            "Test 8: Address of GMO GLOBALSIGN",
            "Address of GMO GLOBALSIGN CERTIFICAT SERVICES PRIVATE LIMITED",
            "Company Attribute Query",
            verifier.verify_company_attribute,
            {"company_name": "GMO GLOBALSIGN", "attribute": "Address"},
            top_k=5
        ),
        
        # Category 4: Product-Based Queries
        TestCase(
            "Test 9: Products to HAL in Gujarat",
            "How many products supplied to HAL in Gujarat",
            "Product Query",
            verifier.verify_product_query,
            {"product_criteria": "HAL Gujarat"},
            top_k=20
        ),
        TestCase(
            "Test 10: Consumable Type Products",
            "show me the companies whose product are of consumable type",
            "Product Query",
            verifier.verify_product_query,
            {"product_criteria": "consumable"},
            top_k=20
        ),
        
        # Category 5: Industry-Specific Queries
        TestCase(
            "Test 11: Drone Manufacturing",
            "Drone manufacturing companies in India",
            "Industry Query",
            verifier.verify_industry_query,
            {"industry_keywords": ["Drone", "UAV", "Unmanned", "Aerospace"]},
            top_k=20
        ),
        TestCase(
            "Test 12: Ship Manufacturing",
            "Ship Manufacturing companies",
            "Industry Query",
            verifier.verify_industry_query,
            {"industry_keywords": ["Ship", "Shipbuilding", "Marine", "Naval"]},
            top_k=20
        ),
        
        # Category 6: Test Facility Queries
        TestCase(
            "Test 13: Chemical Testing Facilities",
            "Companies with test facility for chemical testing",
            "Test Facility Query",
            verifier.verify_test_facility,
            {"facility_type": "chemical"},
            top_k=20
        ),
        
        # Category 7: Research Queries
        TestCase(
            "Test 14: Advanced Materials Research",
            "List companies doing research in advanced materials",
            "Research Query",
            verifier.verify_industry_query,
            {"industry_keywords": ["Material", "Advanced", "Research", "Composite"]},
            top_k=20
        ),
    ]
    
    # Run all test cases
    results = []
    for test_case in test_cases:
        result = run_test_case(engine, verifier, test_case)
        results.append(result)
    
    # Generate summary report
    print("\n" + "="*80)
    print(" TEST SUMMARY REPORT")
    print("="*80)
    
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    total = len(results)
    
    print(f"\nTotal Tests: {total}")
    print(f"✅ Passed: {passed} ({passed/total*100:.1f}%)")
    print(f"❌ Failed: {failed} ({failed/total*100:.1f}%)")
    
    print("\n" + "-"*80)
    print("Detailed Results:")
    print("-"*80)
    
    for i, result in enumerate(results, 1):
        status = "✅ PASS" if result.passed else "❌ FAIL"
        time_str = f"{result.execution_time:.2f}s" if result.execution_time else "N/A"
        print(f"{i:2d}. {status} | {time_str:>7} | {result.name}")
        if result.error:
            print(f"     Error: {result.error}")
    
    print("\n" + "-"*80)
    print("Category Breakdown:")
    print("-"*80)
    
    categories = {}
    for result in results:
        cat = result.category
        if cat not in categories:
            categories[cat] = {"passed": 0, "total": 0}
        categories[cat]["total"] += 1
        if result.passed:
            categories[cat]["passed"] += 1
    
    for cat, stats in categories.items():
        pct = stats["passed"] / stats["total"] * 100
        print(f"{cat:25s}: {stats['passed']}/{stats['total']} ({pct:.1f}%)")
    
    # Save detailed report
    report_file = "test_report.json"
    report_data = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": passed/total*100
        },
        "tests": [
            {
                "name": r.name,
                "query": r.query,
                "category": r.category,
                "passed": r.passed,
                "execution_time": r.execution_time,
                "result_count": len(r.result) if r.result is not None and not r.result.empty else 0,
                "error": r.error
            }
            for r in results
        ]
    }
    
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n📄 Detailed report saved to: {report_file}")
    print(f"📋 Query log saved to: query_log.jsonl")
    
    print("\n" + "="*80)
    print(" TEST SUITE COMPLETE")
    print("="*80)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Test queries for the enhanced query engine with Qwen LLM
Comprehensive test suite covering:
- Filter queries (Defence, MSME, Location)
- Certification queries
- Attribute queries (Address, Contact, PAN)
- Product-based queries
- Industry-specific queries
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

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')
os.environ['LLAMA_LOG_LEVEL'] = '0'  # Suppress llama.cpp verbose output

def run_test_query(engine, query_name, query_text, top_k=20):
    """Run a test query and display results with clean formatting"""
    print(f"\n{'='*80}")
    print(f"🔍 {query_name}")
    print(f"{'='*80}")
    print(f"Question: {query_text}\n")
    
    # Run the query with timing
    print("⏳ Processing query...")
    start_time = time.time()
    response = engine.natural_language_query(query_text, top_k=top_k)
    elapsed_time = time.time() - start_time
    
    # Display LLM-generated answer with timing
    print(f"\n{'='*80}")
    print(f"🤖 QWEN LLM ANSWER (⏱️ {elapsed_time:.2f}s)")
    print(f"{'='*80}")
    print(response["answer"])
    
    # Display results summary
    results = response["results"]
    if not results.empty:
        print(f"\n{'='*80}")
        print(f"📊 TOP {min(10, len(results))} MATCHING COMPANIES")
        print(f"{'='*80}\n")
        
        # Select display columns (no similarity_score for cleaner display)
        display_cols = [c for c in ["CompanyName", "State", "IndustryDomain"] 
                       if c in results.columns]
        
        # Display results in a cleaner format
        for idx, (_, row) in enumerate(results.head(10).iterrows(), 1):
            name = row.get("CompanyName", "N/A")
            state = row.get("State", "N/A")
            domain = row.get("IndustryDomain", "")
            
            print(f"{idx:2d}. {name}")
            print(f"    📍 {state}")
            if domain:
                print(f"    🏭 {domain}")
            print()
        
        print(f"✅ Total found: {len(results)} companies\n")
    else:
        print("\n❌ No results found.\n")

def main():
    print("="*80)
    print("ENHANCED QUERY ENGINE - COMPREHENSIVE TEST SUITE WITH QWEN LLM")
    print("="*80)
    
    # Initialize engine with Qwen LLM
    LLM_PATH = r"D:\CBDPIT\TEMP6\Qwen2.5-3B-Instruct-Q8_0.gguf"
    print(f"\nInitializing query engine with Qwen2.5-3B LLM...")
    print(f"LLM Path: {LLM_PATH}")
    
    # Go to parent directory for correct paths
    parent_dir = Path(__file__).resolve().parent.parent
    os.chdir(parent_dir)
    
    engine = EnhancedQueryEngine(
        views_dir="views", 
        model_name="all-MiniLM-L6-v2",
        llm_model_path=LLM_PATH
    )
    
    # Ensure index is built
    print("Building/checking semantic index...")
    engine.build_semantic_index(force=False)
    
    # Category 1: Filter Queries
    print("\n" + "="*80)
    print("📂 CATEGORY 1: FILTER QUERIES")
    print("="*80)
    
    run_test_query(
        engine,
        "Query 1: Defence Startups",
        "List all defence startups",
        top_k=30
    )
    
    run_test_query(
        engine,
        "Query 2: MSME Companies",
        "List of MSME in India",
        top_k=30
    )
    
    run_test_query(
        engine,
        "Query 3: Companies in Bhopal",
        "Companies based in Bhopal",
        top_k=30
    )
    
    # Category 2: Certification Queries
    print("\n" + "="*80)
    print("🏆 CATEGORY 2: CERTIFICATION QUERIES")
    print("="*80)
    
    run_test_query(
        engine,
        "Query 4: ISO 9001 Certified Companies",
        "List of companies having ISO 9001 certification",
        top_k=30
    )
    
    # Category 3: Company Attribute Queries
    print("\n" + "="*80)
    print("🏢 CATEGORY 3: COMPANY ATTRIBUTE QUERIES")
    print("="*80)
    
    run_test_query(
        engine,
        "Query 5: Address of FLONEX",
        "Address of FLONEX OIL TECHNOLOGIES PRIVATE LIMITED",
        top_k=5
    )
    
    run_test_query(
        engine,
        "Query 6: PAN of K G DENIM Limited",
        "Pan of K G DENIM Limited",
        top_k=5
    )
    
    run_test_query(
        engine,
        "Query 7: Contact Details of MADHYA PRADESH Company",
        "Contact Details of MADHYA PRADESH BHARAT AGRO PRODUCTS LIMITED",
        top_k=5
    )
    
    run_test_query(
        engine,
        "Query 8: Address of GMO GLOBALSIGN",
        "Address of GMO GLOBALSIGN CERTIFICAT SERVICES PRIVATE LIMITED",
        top_k=5
    )
    
    # Category 4: Product-Based Queries
    print("\n" + "="*80)
    print("📦 CATEGORY 4: PRODUCT-BASED QUERIES")
    print("="*80)
    
    run_test_query(
        engine,
        "Query 9: Products Supplied to HAL in Gujarat",
        "How many products supplied to HAL in Gujarat",
        top_k=20
    )
    
    run_test_query(
        engine,
        "Query 10: Consumable Type Products",
        "show me the companies whose product are of consumable type",
        top_k=20
    )
    
    # Category 5: Industry-Specific Queries
    print("\n" + "="*80)
    print("🏭 CATEGORY 5: INDUSTRY-SPECIFIC QUERIES")
    print("="*80)
    
    run_test_query(
        engine,
        "Query 11: Drone Manufacturing Companies",
        "Drone manufacturing companies in India",
        top_k=20
    )
    
    run_test_query(
        engine,
        "Query 12: Ship Manufacturing Companies",
        "Ship Manufacturing companies",
        top_k=20
    )
    
    print("\n" + "="*80)
    print("✅ ALL TEST QUERIES COMPLETE")
    print("="*80)
    print(f"\n📊 Total Queries Tested: 12")
    print("📁 Query log saved to: query_log.jsonl")
    print("\nCategories Covered:")
    print("  • Filter Queries (3)")
    print("  • Certification Queries (1)")
    print("  • Company Attribute Queries (4)")
    print("  • Product-Based Queries (2)")
    print("  • Industry-Specific Queries (2)")

if __name__ == "__main__":
    main()

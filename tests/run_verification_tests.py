#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os

# Fix encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    os.environ['PYTHONIOENCODING'] = 'utf-8'

"""
Quick Test Runner - Runs all requested test queries
Usage: python run_verification_tests.py
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.full_engine_query import EnhancedQueryEngine
import pandas as pd
import warnings
import time

warnings.filterwarnings('ignore')
os.environ['LLAMA_LOG_LEVEL'] = '0'

# Test queries as requested
TEST_QUERIES = [
    ("Defence Startups", "List all defence startups", 30),
    ("MSME in India", "List of MSME in India", 30),
    ("Companies in Bhopal", "Companies based in Bhopal", 30),
    ("ISO 9001 Certification", "List of companies having ISO 9001 certification", 30),
    ("Address of FLONEX", "Address of FLONEX OIL TECHNOLOGIES PRIVATE LIMITED", 5),
    ("Products to HAL Gujarat", "How many products supplied to HAL in Gujarat", 20),
    ("Consumable Products", "show me the companies whose product are of consumable type", 20),
    ("Drone Manufacturing", "Drone manufacturing companies in India", 20),
    ("Ship Manufacturing", "Ship Manufacturing companies", 20),
    ("PAN of K G DENIM", "Pan of K G DENIM Limited", 5),
    ("Contact of MADHYA BHARAT AGRO", "Contact Details of MADHYA BHARAT AGRO PRODUCTS LIMITED", 5),
    ("Address of GMO GLOBALSIGN", "Address of GMO GLOBALSIGN CERTIFICAT SERVICES PRIVATE LIMITED", 5),
    ("Chemical Testing Facilities", "Companies with test facility for chemical testing", 20),
    ("Advanced Materials Research", "List companies doing research in advanced materials", 20),
]

def run_query(engine, name, query, top_k):
    """Run a single query and display results"""
    print(f"\n{'='*80}")
    print(f" {name}")
    print(f"{'='*80}")
    print(f"Query: {query}\n")
    
    start_time = time.time()
    response = engine.natural_language_query(query, top_k=top_k)
    elapsed = time.time() - start_time
    
    print(f"\n⏱ Time: {elapsed:.2f}s")
    print(f"\n{response['answer']}")
    
    results = response["results"]
    if not results.empty:
        print(f"\n📊 Found {len(results)} results")
        print("\nTop 5 Results:")
        print("-" * 80)
        
        for idx, (_, row) in enumerate(results.head(5).iterrows(), 1):
            name = row.get("CompanyName", "N/A")
            city = row.get("City", "N/A")
            state = row.get("State", "N/A")
            
            print(f"\n{idx}. {name}")
            print(f"   Location: {city}, {state}")
            
            # Show relevant fields
            if 'Address' in row and pd.notna(row['Address']):
                addr = str(row['Address'])[:100]
                print(f"   Address: {addr}...")
            if 'PAN' in row and pd.notna(row['PAN']):
                print(f"   PAN: {row['PAN']}")
            if 'ContactNo' in row and pd.notna(row['ContactNo']):
                print(f"   Contact: {row['ContactNo']}")
            if 'Email' in row and pd.notna(row['Email']):
                print(f"   Email: {row['Email']}")
    else:
        print("\n⚠ No results found")
    
    return len(results)

def main():
    print("="*80)
    print("QUERY VERIFICATION TEST RUNNER")
    print("="*80)
    
    # Initialize engine
    parent_dir = Path(__file__).resolve().parent.parent
    os.chdir(parent_dir)
    
    print("\nInitializing query engine...")
    engine = EnhancedQueryEngine(
        views_dir="views",
        model_name="models/all-MiniLM-L6-v2",
        llm_model_path=r"models\Qwen2.5-3B-Instruct-Q8_0.gguf"
    )
    
    print("Building semantic index...")
    engine.build_semantic_index(force=False)
    
    # Run all queries
    results_summary = []
    total_time = 0
    
    for name, query, top_k in TEST_QUERIES:
        try:
            start = time.time()
            count = run_query(engine, name, query, top_k)
            elapsed = time.time() - start
            total_time += elapsed
            
            results_summary.append({
                "name": name,
                "count": count,
                "time": elapsed,
                "status": "✅"
            })
        except Exception as e:
            print(f"\n❌ Error: {e}")
            results_summary.append({
                "name": name,
                "count": 0,
                "time": 0,
                "status": "❌"
            })
    
    # Summary
    print("\n" + "="*80)
    print(" SUMMARY")
    print("="*80)
    
    print(f"\nTotal Queries: {len(TEST_QUERIES)}")
    print(f"Total Time: {total_time:.2f}s")
    print(f"Average Time: {total_time/len(TEST_QUERIES):.2f}s\n")
    
    print("Results:")
    print("-" * 80)
    for r in results_summary:
        print(f"{r['status']} {r['name']:40s} | {r['count']:3d} results | {r['time']:5.2f}s")
    
    print("\n" + "="*80)

if __name__ == "__main__":
    main()

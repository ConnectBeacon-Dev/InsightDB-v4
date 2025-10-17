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
Single Query Verification Tool
Allows testing individual queries with detailed output
Usage: python verify_single_query.py "your query here"
"""

import sys
from pathlib import Path
import argparse

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.full_engine_query import EnhancedQueryEngine
import pandas as pd
import warnings

warnings.filterwarnings('ignore')
os.environ['LLAMA_LOG_LEVEL'] = '0'

def verify_query(engine, query, top_k=20, show_details=True):
    """Run and verify a single query"""
    print(f"\n{'='*80}")
    print(f" QUERY VERIFICATION")
    print(f"{'='*80}")
    print(f"Query: {query}")
    print(f"Top K: {top_k}\n")
    
    print("⏳ Processing query...")
    import time
    start_time = time.time()
    
    response = engine.natural_language_query(query, top_k=top_k)
    
    elapsed = time.time() - start_time
    
    print(f"\n{'='*80}")
    print(f" LLM ANSWER (⏱ {elapsed:.2f}s)")
    print(f"{'='*80}")
    print(response["answer"])
    
    results = response["results"]
    
    if not results.empty:
        print(f"\n{'='*80}")
        print(f" RESULTS ({len(results)} found)")
        print(f"{'='*80}\n")
        
        if show_details:
            # Show all available columns for first result
            print("Available columns in results:")
            print(", ".join(results.columns.tolist()))
            print()
        
        # Display results
        display_count = min(20, len(results))
        for idx, (_, row) in enumerate(results.head(display_count).iterrows(), 1):
            print(f"\n{idx}. {row.get('CompanyName', 'N/A')}")
            print(f"   {'─' * 70}")
            
            # Location info
            city = row.get('CityName', 'N/A')
            state = row.get('State', 'N/A')
            print(f"   📍 Location: {city}, {state}")
            
            # Contact info
            if 'Phone' in row and pd.notna(row['Phone']):
                print(f"   📞 Contact: {row['Phone']}")
            if 'EmailId' in row and pd.notna(row['EmailId']):
                print(f"   📧 Email: {row['EmailId']}")
            
            # Address
            if 'Address' in row and pd.notna(row['Address']):
                addr = str(row['Address'])
                if len(addr) > 100:
                    addr = addr[:100] + "..."
                print(f"   🏢 Address: {addr}")
            
            # Company details
            if 'Pan' in row and pd.notna(row['Pan']):
                print(f"   🆔 PAN: {row['Pan']}")
            if 'CINNumber' in row and pd.notna(row['CINNumber']):
                print(f"   🆔 CIN: {row['CINNumber']}")
            if 'GSTNumber' in row and pd.notna(row['GSTNumber']):
                print(f"   🆔 GST: {row['GSTNumber']}")
            if 'IndustryDomainName' in row and pd.notna(row['IndustryDomainName']):
                print(f"   🏭 Industry: {row['IndustryDomainName']}")
            if 'Organisation_Type' in row and pd.notna(row['Organisation_Type']):
                print(f"   🏢 Type: {row['Organisation_Type']}")
            if 'CompanyScale' in row and pd.notna(row['CompanyScale']):
                print(f"   📊 Scale: {row['CompanyScale']}")
            
            # Additional info
            if 'Website' in row and pd.notna(row['Website']):
                print(f"   🌐 Website: {row['Website']}")
            if 'CompanyStatus' in row and pd.notna(row['CompanyStatus']):
                print(f"   📊 Status: {row['CompanyStatus']}")
            if 'CoreExpertiseName' in row and pd.notna(row['CoreExpertiseName']):
                print(f"   💼 Expertise: {row['CoreExpertiseName']}")
        
        if len(results) > display_count:
            print(f"\n... and {len(results) - display_count} more results")
        
        # Summary statistics
        print(f"\n{'='*80}")
        print(f" STATISTICS")
        print(f"{'='*80}")
        print(f"Total Results: {len(results)}")
        
        if 'State' in results.columns:
            state_counts = results['State'].value_counts().head(5)
            print(f"\nTop States:")
            for state, count in state_counts.items():
                print(f"  • {state}: {count}")
        
        if 'IndustryDomainName' in results.columns:
            domain_counts = results['IndustryDomainName'].value_counts().head(5)
            print(f"\nTop Industries:")
            for domain, count in domain_counts.items():
                if pd.notna(domain):
                    print(f"  • {domain}: {count}")
        
        if 'Organisation_Type' in results.columns:
            type_counts = results['Organisation_Type'].value_counts().head(5)
            print(f"\nTop Organization Types:")
            for org_type, count in type_counts.items():
                if pd.notna(org_type):
                    print(f"  • {org_type}: {count}")
        
    else:
        print("\n⚠ No results found")
    
    print(f"\n{'='*80}")
    print(f" Query completed in {elapsed:.2f}s")
    print(f"{'='*80}\n")
    
    return results

def main():
    parser = argparse.ArgumentParser(
        description="Verify a single query against InsightDB",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python verify_single_query.py "List all defence startups"
  python verify_single_query.py "Companies in Bhopal" --top-k 50
  python verify_single_query.py "Address of FLONEX OIL TECHNOLOGIES" --no-details
        """
    )
    
    parser.add_argument(
        'query',
        nargs='?',
        help='Query to verify (if not provided, will use interactive mode)'
    )
    parser.add_argument(
        '--top-k',
        type=int,
        default=20,
        help='Number of results to return (default: 20)'
    )
    parser.add_argument(
        '--no-details',
        action='store_true',
        help='Hide detailed column information'
    )
    
    args = parser.parse_args()
    
    # Initialize engine
    parent_dir = Path(__file__).resolve().parent.parent
    os.chdir(parent_dir)
    
    print("="*80)
    print("SINGLE QUERY VERIFICATION TOOL")
    print("="*80)
    print("\nInitializing query engine...")
    
    engine = EnhancedQueryEngine(
        views_dir="views",
        model_name="models/all-MiniLM-L6-v2",
        llm_model_path=r"models\Qwen2.5-3B-Instruct-Q8_0.gguf"
    )
    
    print("Building semantic index...")
    engine.build_semantic_index(force=False)
    print("✓ Engine ready\n")
    
    if args.query:
        # Single query mode
        verify_query(engine, args.query, args.top_k, not args.no_details)
    else:
        # Interactive mode
        print("="*80)
        print("INTERACTIVE MODE")
        print("="*80)
        print("Enter queries to verify (or 'quit' to exit)")
        print()
        
        while True:
            try:
                query = input("Query> ").strip()
                
                if not query:
                    continue
                
                if query.lower() in ['quit', 'exit', 'q']:
                    print("\nGoodbye!")
                    break
                
                verify_query(engine, query, args.top_k, not args.no_details)
                
            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}\n")

if __name__ == "__main__":
    main()

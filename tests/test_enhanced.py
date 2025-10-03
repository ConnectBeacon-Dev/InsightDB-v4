#!/usr/bin/env python3
from enhanced_query_engine import EnhancedQueryEngine

engine = EnhancedQueryEngine()

# Test the fixed company address query
response = engine.natural_language_query("Industry type of FLONEX OIL TECHNOLOGIES")

print(f"\nFound: {response['count']} results")
print(f"Answer: {response['answer']}")

if response['count'] > 0:
    print("\nCompany details:")
    print(response['results'])
    #print(response['results'][['CompanyName', 'Address', 'State']].to_string())

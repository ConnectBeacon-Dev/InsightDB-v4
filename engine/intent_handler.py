#!/usr/bin/env python3
"""
Intent Handler for Natural Language Queries
Uses intents_reference.json to map queries to filters and ETL columns
"""

import re
import json
from pathlib import Path
from typing import Dict, Any, Optional

# Try to import fuzzy matching (optional)
try:
    from fuzzywuzzy import process
    FUZZY_AVAILABLE = True
except ImportError:
    FUZZY_AVAILABLE = False


class IntentHandler:
    """Handles intent detection and parameter extraction from natural language queries"""
    
    def __init__(self, intents_file: str = "intents_reference.json"):
        """Initialize with intent patterns from JSON file"""
        self.intents = self._load_intents(intents_file)
        
    def _load_intents(self, intents_file: str) -> Dict[str, Any]:
        """Load intent patterns from JSON reference file"""
        try:
            intents_path = Path(intents_file)
            if intents_path.exists():
                with open(intents_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                print(f"  Intent reference file {intents_file} not found")
                return {}
        except Exception as e:
            print(f"  Error loading intent patterns: {e}")
            return {}
    
    def analyze_query(self, query: str) -> Dict[str, Any]:
        """
        Analyze a natural language query and return intent with parameters.
        Returns dict with:
        - intent: "filter_list", "company_attribute", or "generic"
        - params: dict with filter_type, etl_column, value (location), etc.
        """
        q_lower = query.lower()
        
        # 1. Check for company attribute queries (highest priority)
        attr_intent = self._check_attribute_query(q_lower)
        if attr_intent:
            return attr_intent
        
        # 2. Check for classification-based filters (government, msme, etc.)
        # This MUST come before location-only check
        filter_intent = self._check_classification_filters(q_lower)
        if filter_intent:
            return filter_intent
        
        # 3. Check for industry/location combined queries
        if self._has_industry_and_location(q_lower):
            return {"intent": "generic", "params": {"use_semantic_search": True}}
        
        # 4. Check for location-only queries (only if no classification filter matched)
        location = self._extract_location(q_lower)
        if location and not self._has_industry_keywords(q_lower) and not self._has_classification_keywords(q_lower):
            return {
                "intent": "filter_list",
                "params": {
                    "filter_type": "location",
                    "value": location,
                    "etl_column": "State"  # or City
                }
            }
        
        # 5. Default to generic semantic search
        return {"intent": "generic", "params": {}}
    
    def _has_classification_keywords(self, query: str) -> bool:
        """Check if query contains classification keywords (government, msme, etc.)"""
        classification_keywords = [
            'government', 'govt', 'psu', 'public sector',
            'msme', 'micro', 'small', 'medium',
            'listed', 'private', 'union', 'state', 'central'
        ]
        return any(keyword in query for keyword in classification_keywords)
    
    def _check_attribute_query(self, query: str) -> Optional[Dict[str, Any]]:
        """Check if query is asking for a specific company attribute"""
        if not self.intents.get("attribute_queries"):
            return None
        
        attr_patterns = self.intents["attribute_queries"]["patterns"]
        
        # Try each attribute pattern
        for pattern_info in attr_patterns:
            attribute = pattern_info["attribute"]
            keywords = pattern_info["keywords"]
            
            # Check if any keyword matches
            for keyword in keywords:
                # Flexible pattern: "{keyword} [optional words] of/for {company_name}"
                # Handles: "GST of X", "GST Number of X", "PAN Number of X", etc.
                keyword_escaped = re.escape(keyword)
                pattern = rf"{keyword_escaped}(?:\s+(?:number|no\.?|code))?\s+(?:of|for)\s+(.+)"
                m = re.search(pattern, query, re.IGNORECASE)
                if m:
                    company_name = m.group(1).strip(" ?.,'\"")
                    return {
                        "intent": "company_attribute",
                        "params": {
                            "company_name": company_name,
                            "attribute": attribute,
                            "etl_columns": pattern_info.get("etl_columns", [])
                        }
                    }
        
        return None
    
    def _check_classification_filters(self, query: str) -> Optional[Dict[str, Any]]:
        """Check if query matches any classification-based filter"""
        if not self.intents.get("classification_based_intents"):
            return None
        
        classifications = self.intents["classification_based_intents"]
        location = self._extract_location(query)
        
        # Check each classification category
        for category_name, category_data in classifications.items():
            if "patterns" not in category_data:
                continue
            
            for pattern_info in category_data["patterns"]:
                keywords = pattern_info.get("keywords", [])
                filter_type = pattern_info.get("filter_type")
                etl_column = pattern_info.get("etl_column")
                
                # Check if any keyword matches
                for keyword in keywords:
                    # Make keyword matching flexible: handle plurals and word boundaries
                    # Convert "government company" to match "government compan" (catches company/companies)
                    keyword_parts = keyword.lower().split()
                    
                    # Check if all parts of the keyword are present in query
                    all_parts_found = True
                    for part in keyword_parts:
                        # For words ending in 'y', also match 'ies' (company -> companies)
                        if part == 'company':
                            if not re.search(r'\bcompan(y|ies)', query, re.IGNORECASE):
                                all_parts_found = False
                                break
                        else:
                            # For other words, just check if present
                            if part not in query:
                                all_parts_found = False
                                break
                    
                    if all_parts_found:
                        params = {
                            "filter_type": filter_type,
                            "etl_column": etl_column
                        }
                        
                        # Add location if present
                        if location:
                            params["value"] = location
                        
                        # Add size value if present (for company_size filters)
                        if "size_value" in pattern_info:
                            params["size"] = pattern_info["size_value"]
                        
                        # Add industry value if present
                        if "industry_value" in pattern_info:
                            params["industry"] = pattern_info["industry_value"]
                        
                        return {"intent": "filter_list", "params": params}
        
        return None
    
    def _extract_location(self, query: str) -> str:
        """Extract location (city or state) from query with fuzzy matching for typos"""
        # Try standard location patterns first
        loc_match = re.search(r'\b(?:in|from|at|based\s+in)\s+([a-zA-Z\s]+?)(?:\s|$)', query)
        extracted_location = ""
        
        if loc_match:
            extracted_location = loc_match.group(1).strip()
            # Exclude common words
            if extracted_location.lower() in ["india", "the", "a", "an", "all", "any"]:
                extracted_location = ""
        
        # Get known locations from intents
        if not self.intents.get("location_filters"):
            return extracted_location
        
        loc_data = self.intents["location_filters"]
        states = loc_data.get("major_states", [])
        cities = loc_data.get("major_cities", [])
        all_locations = states + cities
        
        # First try exact match
        for location in all_locations:
            if location.lower() in query.lower():
                return location
        
        # If extracted location exists but no exact match, try fuzzy matching for typos
        if extracted_location and FUZZY_AVAILABLE:
            # Find closest match using fuzzy matching (handles typos like "Karnatka" -> "Karnataka")
            best_match = process.extractOne(extracted_location, all_locations, score_cutoff=80)
            if best_match:
                return best_match[0]
        
        return extracted_location
    
    def _has_industry_keywords(self, query: str) -> bool:
        """Check if query contains industry keywords"""
        industry_keywords = [
            'electrical', 'electronics', 'pharma', 'pharmaceutical', 'automotive',
            'textile', 'steel', 'metal', 'chemical', 'food', 'software', 'it',
            'defence', 'defense', 'aerospace', 'plastic', 'machinery', 'construction'
        ]
        return any(keyword in query for keyword in industry_keywords)
    
    def _has_industry_and_location(self, query: str) -> bool:
        """Check if query has both industry and location (use semantic search)"""
        has_industry = self._has_industry_keywords(query)
        location = self._extract_location(query)
        return has_industry and bool(location)


# Standalone function for easy import
def analyze_intent(query: str, intents_file: str = "intents_reference.json") -> Dict[str, Any]:
    """Convenience function to analyze a query without creating IntentHandler instance"""
    handler = IntentHandler(intents_file)
    return handler.analyze_query(query)


if __name__ == "__main__":
    # Test the intent handler
    handler = IntentHandler()
    
    test_queries = [
        "Government companies in Karnataka",
        "MSME companies in Pune",
        "Address of HEG LIMITED",
        "Listed companies in India",
        "Electrical companies in Pune",
        "Defence companies",
        "Private companies in Bangalore"
    ]
    
    print("Testing Intent Handler:\n")
    for query in test_queries:
        intent = handler.analyze_query(query)
        print(f"Query: {query}")
        print(f"Intent: {intent}")
        print()

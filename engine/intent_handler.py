#!/usr/bin/env python3
"""
Simplified Intent Handler for Natural Language Queries
Only handles location and classification filters - everything else uses semantic search
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
    """Simplified intent handler - only location and classification filters"""
    
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
        Query analysis - handles company attributes, location filters, and classification.
        
        Returns dict with:
        - intent: "company_attribute", "filter_list", or "generic"
        - params: dict with company_name, attribute, filter_type, value, etc.
        """
        q_lower = query.lower()
        
        # 1. Check for company attribute queries (highest priority)
        attr_intent = self._check_company_attributes(q_lower)
        if attr_intent:
            return attr_intent
        
        # 2. Check for classification-based filters (government, msme, etc.)
        filter_intent = self._check_classification_filters(q_lower)
        if filter_intent:
            return filter_intent
        
        # 3. Check for industry/location combined queries -> semantic search
        if self._has_industry_and_location(q_lower):
            return {"intent": "generic", "params": {"use_semantic_search": True}}
        
        # 4. Check for location-only queries
        location = self._extract_location(q_lower)
        if location:
            # Check if query has meaningful content beyond just location
            has_content_beyond_location = self._has_content_beyond_location(q_lower, location)
            
            if has_content_beyond_location:
                # Route to semantic search for location + anything else
                return {"intent": "generic", "params": {"use_semantic_search": True}}
            else:
                # Pure location query - use CSV filter
                return {
                    "intent": "filter_list",
                    "params": {
                        "filter_type": "location",
                        "value": location,
                        "etl_column": "State"
                    }
                }
        
        # 5. Default to semantic search for everything else
        return {"intent": "generic", "params": {}}
    
    def _has_content_beyond_location(self, query: str, location: str) -> bool:
        """
        Check if query has meaningful content words beyond just location.
        This helps distinguish:
        - "companies in Maharashtra" (location-only) -> CSV filter
        - "drone companies in Maharashtra" (location + product) -> semantic search
        """
        # Remove common stop words and location-related words
        stop_words = {
            'in', 'at', 'from', 'of', 'the', 'a', 'an', 'and', 'or', 'for',
            'companies', 'company', 'list', 'show', 'find', 'get', 'all',
            'based', 'located', 'present'
        }
        
        # Tokenize and clean
        words = query.lower().split()
        content_words = []
        
        for word in words:
            # Remove punctuation
            word = word.strip('.,?!;:')
            # Skip if it's a stop word, location, or empty
            if word and word not in stop_words and word not in location.lower().split():
                content_words.append(word)
        
        # If there are content words beyond location, use semantic search
        return len(content_words) > 0
    
    def _check_company_attributes(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Check if query is asking for specific company attributes.
        Examples: "PAN of X", "Contact address of Y", "Products made by Z"
        """
        # Company attribute patterns (order matters - more specific first)
        attr_patterns = [
            (r"(?:contact\s+)?(?:address|location)\s+(?:of|for)\s+(.+)", "address"),
            (r"(?:contact|phone|email|details?)\s+(?:of|for)\s+(.+)", "contact"),
            (r"(?:pan|cin|gstin?|registration)\s+(?:of|for)\s+(.+)", "registration"),
            (r"(?:industry\s+type|industry|domain|sector)\s+(?:of|for)\s+(.+)", "industry"),
            (r"(?:products?|services?)\s+(?:of|for|made\s+by|manufactured\s+by)\s+(.+)", "products"),
            (r"(?:turnover|revenue|sales)\s+(?:of|for)\s+(.+)", "turnover"),
            (r"(?:test\s+facilit(?:y|ies))\s+(?:of|for)\s+(.+)", "test_facilities"),
            (r"(?:r&d\s+facilit(?:y|ies)|research\s+facilit(?:y|ies))\s+(?:of|for)\s+(.+)", "rd_facilities"),
        ]
        
        for pattern, attr_type in attr_patterns:
            match = re.search(pattern, query)
            if match:
                company_name = match.group(1).strip(" ?,.")
                return {
                    "intent": "company_attribute",
                    "params": {
                        "company_name": company_name,
                        "attribute": attr_type
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
        """Check if query contains industry/product/manufacturing keywords"""
        industry_keywords = [
            'electrical', 'electronics', 'pharma', 'pharmaceutical', 'automotive',
            'textile', 'steel', 'metal', 'chemical', 'food', 'software', 'it',
            'defence', 'defense', 'aerospace', 'plastic', 'machinery', 'construction'
        ]
        
        # Product/manufacturing keywords
        product_keywords = [
            'making', 'manufacturing', 'manufacturer', 'producer', 'producing',
            'supplier', 'maker', 'fabricator', 'assembler',
            # Specific products
            'drone', 'uav', 'uas', 'robot', 'sensor', 'component', 'part',
            'equipment', 'device', 'system', 'product', 'material'
        ]
        
        return any(keyword in query for keyword in industry_keywords + product_keywords)
    
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
    # Test the simplified intent handler
    handler = IntentHandler()
    
    test_queries = [
        "Government companies in Karnataka",  # Classification filter
        "MSME companies in Pune",             # Classification filter
        "Companies in Bhopal",                # Location filter
        "Listed companies in India",          # Classification filter
        "Electrical companies in Pune",       # Semantic search (industry + location)
        "Defence companies",                  # Semantic search
        "Address of HEG LIMITED",             # Semantic search (no attribute detection)
        "Contact details of ABC Corp",        # Semantic search (no attribute detection)
        "Drone manufacturing companies"       # Semantic search
    ]
    
    print("Testing Simplified Intent Handler:\n")
    print("Only handles: Location filters and Classification filters")
    print("Everything else -> Semantic Search\n")
    print("="*80 + "\n")
    
    for query in test_queries:
        intent = handler.analyze_query(query)
        print(f"Query: {query}")
        print(f"Intent: {intent['intent']}")
        if intent['params']:
            print(f"Params: {intent['params']}")
        print()

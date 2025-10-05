#!/usr/bin/env python3
"""
LLM-based intelligent industry classifier using semantic similarity
Uses the existing sentence transformer for accurate classification
"""
import numpy as np
from sentence_transformers import SentenceTransformer
from typing import Dict, Optional, List
import warnings
warnings.filterwarnings('ignore')

# Industry descriptions for semantic matching
INDUSTRY_DESCRIPTIONS = {
    'Pharmaceuticals': [
        'pharmaceutical drugs medicines tablets capsules healthcare medical vaccines diagnostics',
        'biotech biotechnology clinical therapeutic antibiotic injection syrup medicinal pharmaceutical industry',
        'drug manufacturer medicine production pharmaceutical research healthcare products'
    ],
    'Electrical & Electronics': [
        'electrical electronics power cables transformers motors generators batteries switchgear',
        'electronic components circuits LED lighting panels meters relays switches electrical equipment',
        'power generation transmission distribution electrical machinery inverters UPS solar energy'
    ],
    'Automotive': [
        'automotive vehicles cars trucks automobiles auto parts components manufacturing',
        'vehicle engines brakes gears axles suspension steering automotive industry',
        'automobiles motor vehicles transportation automotive components parts suppliers'
    ],
    'Aerospace & Defence': [
        'aerospace defence military aviation aircraft missiles radar weapons systems',
        'defense equipment ammunition combat fighter helicopter submarine naval warships',
        'aerospace manufacturing aircraft components defense technology military equipment'
    ],
    'Textiles': [
        'textile fabrics garments apparel clothing fibers cotton polyester yarn',
        'textile manufacturing weaving spinning fabric production textile industry',
        'clothing garments fabric textiles apparel manufacturing fashion industry'
    ],
    'Steel & Metals': [
        'steel iron metals aluminium copper brass alloys casting forging',
        'metallurgical foundry metal fabrication steel manufacturing iron products',
        'metal processing steel production aluminium copper zinc metal industry'
    ],
    'Chemicals': [
        'chemicals polymers resins coatings paints adhesives solvents chemical products',
        'chemical manufacturing industrial chemicals organic inorganic chemical industry',
        'specialty chemicals fertilizers acids alkalis chemical processing'
    ],
    'Food & Beverages': [
        'food beverages dairy agricultural products grain flour oil spices',
        'food processing beverage manufacturing edible products bakery confectionery',
        'agricultural products food industry dairy meat beverages drinks'
    ],
    'IT & Software': [
        'information technology software IT services digital technology computing',
        'software development technology solutions IT consulting cloud computing',
        'computer technology digital services IT industry software products'
    ],
    'Plastics': [
        'plastics polymer PVC polyethylene polypropylene plastic products moulding',
        'plastic manufacturing injection moulding extrusion plastic processing',
        'polymer products plastic materials plastic fabrication plastic industry'
    ],
    'Machinery & Equipment': [
        'machinery equipment tools pumps compressors valves bearings industrial machinery',
        'mechanical equipment manufacturing machinery tools instruments',
        'industrial equipment machinery manufacturing mechanical systems'
    ],
    'Construction & Engineering': [
        'construction engineering infrastructure building cement concrete civil works',
        'construction materials engineering services infrastructure development',
        'building construction civil engineering structural engineering'
    ],
}


class LLMIndustryClassifier:
    """
    Intelligent industry classifier using semantic similarity with sentence transformers
    Fast, accurate, and works with minimal data
    """
    
    def __init__(self, model_name='models/all-MiniLM-L6-v2'):
        """Initialize with the sentence transformer model"""
        print(f"      Loading LLM classifier: {model_name}...")
        self.model = SentenceTransformer(model_name)
        
        # Pre-compute embeddings for industry descriptions
        self.industry_embeddings = {}
        for industry, descriptions in INDUSTRY_DESCRIPTIONS.items():
            # Get embeddings for all descriptions of this industry
            embeddings = self.model.encode(descriptions, show_progress_bar=False)
            # Average them for a robust industry representation
            self.industry_embeddings[industry] = np.mean(embeddings, axis=0)
        
        print(f"      LLM classifier ready with {len(self.industry_embeddings)} industries")
    
    def classify_company(
        self, 
        company_name: str, 
        address: str = '',
        certifications: List[str] = None,
        context: str = '',
        confidence_threshold: float = 0.35
    ) -> Optional[str]:
        """
        Classify a company using semantic similarity
        
        Args:
            company_name: Company name
            address: Company address
            certifications: List of certifications
            context: Additional context (e.g., from industry domain field)
            confidence_threshold: Minimum similarity score (0-1)
        
        Returns:
            Industry name or None if confidence too low
        """
        # Build context string
        parts = [company_name]
        if context and context not in ['', 'Other', 'nan', 'NaN']:
            parts.append(context)
        if address:
            parts.append(address)
        if certifications:
            parts.extend(certifications[:3])  # Limit to avoid too much noise
        
        text = ' '.join(parts)
        
        # Get embedding for the company context
        text_embedding = self.model.encode(text, show_progress_bar=False)
        
        # Calculate similarity with each industry
        similarities = {}
        for industry, industry_emb in self.industry_embeddings.items():
            # Cosine similarity
            similarity = np.dot(text_embedding, industry_emb) / (
                np.linalg.norm(text_embedding) * np.linalg.norm(industry_emb)
            )
            similarities[industry] = similarity
        
        # Get best match
        best_industry = max(similarities.items(), key=lambda x: x[1])
        
        if best_industry[1] >= confidence_threshold:
            return best_industry[0]
        
        return None
    
    def classify_batch(
        self, 
        companies: List[Dict],
        confidence_threshold: float = 0.35,
        batch_size: int = 32
    ) -> List[Optional[str]]:
        """
        Classify multiple companies efficiently in batches
        
        Args:
            companies: List of dicts with keys: name, address, certifications, context
            confidence_threshold: Minimum similarity score
            batch_size: Number of companies to process at once
        
        Returns:
            List of industry names (or None)
        """
        results = []
        
        # Build context texts
        texts = []
        for comp in companies:
            parts = [comp.get('name', '')]
            if comp.get('context') and comp['context'] not in ['', 'Other', 'nan', 'NaN']:
                parts.append(comp['context'])
            if comp.get('address'):
                parts.append(comp['address'])
            if comp.get('certifications'):
                parts.extend(comp['certifications'][:3])
            texts.append(' '.join(parts))
        
        # Process in batches
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i+batch_size]
            
            # Get embeddings for batch
            batch_embeddings = self.model.encode(batch_texts, show_progress_bar=False, batch_size=batch_size)
            
            # Classify each in batch
            for text_emb in batch_embeddings:
                similarities = {}
                for industry, industry_emb in self.industry_embeddings.items():
                    similarity = np.dot(text_emb, industry_emb) / (
                        np.linalg.norm(text_emb) * np.linalg.norm(industry_emb)
                    )
                    similarities[industry] = similarity
                
                best = max(similarities.items(), key=lambda x: x[1])
                if best[1] >= confidence_threshold:
                    results.append(best[0])
                else:
                    results.append(None)
        
        return results


# Singleton instance
_classifier = None

def get_classifier() -> LLMIndustryClassifier:
    """Get or create the classifier instance (singleton pattern)"""
    global _classifier
    if _classifier is None:
        _classifier = LLMIndustryClassifier()
    return _classifier

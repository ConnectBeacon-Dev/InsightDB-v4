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
Download sentence-transformer model for offline use
This ensures the model is cached locally and doesn't need internet later
Only downloads if model is not already present
"""

from sentence_transformers import SentenceTransformer
from pathlib import Path

def check_model_exists(cache_dir, model_name):
    """Check if model already exists in cache"""
    model_path = cache_dir / model_name
    if model_path.exists():
        # Check for key files
        config_file = model_path / "config.json"
        if config_file.exists():
            return True
    return False

def download_model():
    """Download and cache the embedding model if not already present"""
    model_name = "all-MiniLM-L6-v2"
    cache_dir = Path("models")
    cache_dir.mkdir(exist_ok=True)
    
    # Check if model already exists
    if check_model_exists(cache_dir, model_name):
        print(f" Model already exists: {cache_dir / model_name}")
        print(f"Skipping download.")
        print()
        
        # Test the existing model
        try:
            print("Testing existing model...")
            model = SentenceTransformer(str(cache_dir / model_name))
            test_embedding = model.encode(["test sentence"])
            print(f" Model works! (embedding dimensions: {len(test_embedding[0])})")
            return True
        except Exception as e:
            print(f"  Existing model corrupted: {e}")
            print("Will re-download...")
            # Continue to download
    
    print(f"Downloading embedding model: {model_name}")
    print(f"This will be cached in: {cache_dir.absolute()}")
    print("This is a one-time download (~90 MB)")
    print()
    
    try:
        # Download and cache the model
        model = SentenceTransformer(model_name, cache_folder=str(cache_dir))
        
        print()
        print(f" Model downloaded successfully!")
        print(f" Cached in: {cache_dir.absolute()}")
        print()
        print("You can now:")
        print("1. Transfer the 'models' folder to an offline machine")
        print("2. Use --model models/all-MiniLM-L6-v2 in your queries")
        print()
        
        # Test the model
        print("Testing model...")
        test_embedding = model.encode(["test sentence"])
        print(f" Model works! (embedding dimensions: {len(test_embedding[0])})")
        
    except Exception as e:
        print(f" Error downloading model: {e}")
        print()
        print("Troubleshooting:")
        print("1. Check internet connection")
        print("2. Try: pip install sentence-transformers --upgrade")
        print("3. Check firewall settings")
        return False
    
    return True

if __name__ == "__main__":
    success = download_model()
    exit(0 if success else 1)

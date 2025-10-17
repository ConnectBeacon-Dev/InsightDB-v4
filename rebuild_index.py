"""
Force rebuild the semantic index with new product weighting.
Run this script, then restart your Flask app.
"""
import shutil
from pathlib import Path
from engine.full_engine_query import EnhancedQueryEngine

# Delete old index
index_dir = Path("views/.sem_index")
if index_dir.exists():
    print(f"Deleting old index at {index_dir}...")
    shutil.rmtree(index_dir)
    print("✓ Old index deleted")
else:
    print("No existing index found")

# Rebuild with new product weighting
print("\nRebuilding semantic index with boosted product weight...")
engine = EnhancedQueryEngine()
engine.build_semantic_index(force=True)

print("\n" + "="*60)
print("✓ Index rebuilt successfully!")
print("="*60)
print("\nNow restart your Flask app:")
print("  1. Stop the current Flask app (Ctrl+C)")
print("  2. Run: python.exe .\\app_rag_chat.py")
print("\nThen test: 'drone making companies in Maharashstra'")

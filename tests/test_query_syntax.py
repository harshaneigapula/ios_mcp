import chromadb
import os
import shutil
from chromadb.config import Settings

# Setup temporary DB
DB_PATH = "./test_chroma_db"
if os.path.exists(DB_PATH):
    shutil.rmtree(DB_PATH)

client = chromadb.PersistentClient(path=DB_PATH)
collection = client.get_or_create_collection(name="test_files")

# Insert test data
metadata = [
    {"id": "1", "ISO": 100, "Make": "Apple", "Model": "iPhone 12"},
    {"id": "2", "ISO": 800, "Make": "Apple", "Model": "iPhone 13"},
    {"id": "3", "ISO": 50, "Make": "Canon", "Model": "EOS R5"},
    {"id": "4", "ISO": 200, "Make": "Sony", "Model": "A7III"},
]

ids = [m["id"] for m in metadata]
docs = [f"File {m['id']}" for m in metadata]
metas = [{k: v for k, v in m.items() if k != "id"} for m in metadata]

collection.add(ids=ids, documents=docs, metadatas=metas)

print("--- Data Inserted ---")

# Test Cases
tests = [
    {
        "name": "Simple Equality",
        "where": {"Make": "Apple"},
        "expected_count": 2
    },
    {
        "name": "Greater Than",
        "where": {"ISO": {"$gt": 100}},
        "expected_count": 2 # 800, 200
    },
    {
        "name": "Greater Than or Equal",
        "where": {"ISO": {"$gte": 100}},
        "expected_count": 3 # 100, 800, 200
    },
    {
        "name": "AND Condition (Implicit)",
        "where": {"Make": "Apple", "ISO": 100},
        "expected_count": 1
    },
    {
        "name": "AND Operator ($and)",
        "where": {
            "$and": [
                {"Make": "Apple"},
                {"ISO": {"$gte": 100}}
            ]
        },
        "expected_count": 2 # Both apples are >= 100 (100, 800)
    },
     {
        "name": "OR Operator ($or)",
        "where": {
            "$or": [
                {"Make": "Canon"},
                {"ISO": 800}
            ]
        },
        "expected_count": 2 # Canon (50) + Apple (800)
    }
]

for t in tests:
    print(f"Running: {t['name']}")
    try:
        results = collection.get(where=t['where'])
        count = len(results['ids'])
        if count == t['expected_count']:
            print(f"  PASS: Got {count} results.")
        else:
            print(f"  FAIL: Expected {t['expected_count']}, got {count}. Results: {results['metadatas']}")
    except Exception as e:
        print(f"  ERROR: {e}")

# Cleanup
if os.path.exists(DB_PATH):
    shutil.rmtree(DB_PATH)

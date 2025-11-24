import chromadb
import os
import shutil
import pytest
from src.database import Database

# Setup temporary DB
DB_PATH = "./test_chroma_db_agg"

@pytest.fixture(scope="module")
def db():
    if os.path.exists(DB_PATH):
        shutil.rmtree(DB_PATH)
    
    db_instance = Database(db_path=DB_PATH)
    
    # Insert test data
    metadata = [
        {"SourceFile": "/tmp/1.jpg", "ISO": 100, "Make": "Apple", "Model": "iPhone 12", "CreationDate": "2023-01-01"},
        {"SourceFile": "/tmp/2.jpg", "ISO": 800, "Make": "Apple", "Model": "iPhone 13", "CreationDate": "2023-02-01"},
        {"SourceFile": "/tmp/3.jpg", "ISO": 50, "Make": "Canon", "Model": "EOS R5", "CreationDate": "2022-12-01"},
        {"SourceFile": "/tmp/4.jpg", "ISO": 200, "Make": "Sony", "Model": "A7III", "CreationDate": "2023-03-01"},
        {"SourceFile": "/tmp/5.jpg", "ISO": 100, "Make": "Apple", "Model": "iPhone 12", "CreationDate": "2023-01-02"},
        {"SourceFile": "/tmp/6.jpg", "ISO": 50, "Make": "Canon", "Model": "EOS R5", "CreationDate": "2022-12-02"},
    ]
    
    db_instance.upsert_files(metadata)
    yield db_instance
    
    # Cleanup
    if os.path.exists(DB_PATH):
        shutil.rmtree(DB_PATH)

def test_match_count(db):
    pipeline = [
        {"$match": {"Make": "Apple"}},
        {"$count": "total"}
    ]
    results = db.aggregate(pipeline)
    assert len(results) == 1
    assert results[0]["total"] == 3

def test_group_sum(db):
    # Group by Model, count occurrences
    pipeline = [
        {"$group": {"_id": "$Model", "count": {"$sum": 1}}}
    ]
    results = db.aggregate(pipeline)
    # iPhone 12: 2, iPhone 13: 1, EOS R5: 2, A7III: 1
    counts = {r["_id"]: r["count"] for r in results}
    assert counts["iPhone 12"] == 2
    assert counts["EOS R5"] == 2
    assert counts["iPhone 13"] == 1

def test_group_avg(db):
    # Group by Make, avg ISO
    pipeline = [
        {"$group": {"_id": "$Make", "avg_iso": {"$avg": "$ISO"}}}
    ]
    results = db.aggregate(pipeline)
    avgs = {r["_id"]: r["avg_iso"] for r in results}
    # Apple: (100+800+100)/3 = 333.33
    # Canon: (50+50)/2 = 50
    assert abs(avgs["Apple"] - 333.33) < 0.1
    assert avgs["Canon"] == 50

def test_pipeline_filter_group_filter_sort(db):
    # 1. Match Make=Apple or Canon
    # 2. Group by Model, avg ISO
    # 3. Match avg ISO < 100
    # 4. Sort by avg ISO desc
    
    pipeline = [
        {"$match": {"$or": [{"Make": "Apple"}, {"Make": "Canon"}]}},
        {"$group": {"_id": "$Model", "avg_iso": {"$avg": "$ISO"}}},
        {"$match": {"avg_iso": {"$lt": 200}}}, # Should keep iPhone 12 (100) and EOS R5 (50)
        {"$sort": {"avg_iso": -1}} # iPhone 12 first
    ]
    
    results = db.aggregate(pipeline)
    assert len(results) == 2
    assert results[0]["_id"] == "iPhone 12"
    assert results[0]["avg_iso"] == 100
    assert results[1]["_id"] == "EOS R5"
    assert results[1]["avg_iso"] == 50

def test_project(db):
    pipeline = [
        {"$match": {"Model": "iPhone 13"}},
        {"$project": {"ISO": 1, "_id": 0}}
    ]
    results = db.aggregate(pipeline)
    assert len(results) == 1
    assert "ISO" in results[0]
    assert "Model" not in results[0]
    assert "_id" not in results[0]

def test_limit_skip(db):
    pipeline = [
        {"$sort": {"ISO": 1}}, # 50, 50, 100, 100, 200, 800
        {"$skip": 2}, # Skip 50, 50
        {"$limit": 2} # Take 100, 100
    ]
    results = db.aggregate(pipeline)
    assert len(results) == 2
    assert results[0]["ISO"] == 100

def test_group_min_max(db):
    # Group by Make, min/max ISO
    pipeline = [
        {"$group": {
            "_id": "$Make", 
            "min_iso": {"$min": "$ISO"},
            "max_iso": {"$max": "$ISO"}
        }}
    ]
    results = db.aggregate(pipeline)
    stats = {r["_id"]: r for r in results}
    
    # Apple: 100, 800, 100 -> min 100, max 800
    assert stats["Apple"]["min_iso"] == 100
    assert stats["Apple"]["max_iso"] == 800
    
    # Canon: 50, 50 -> min 50, max 50
    assert stats["Canon"]["min_iso"] == 50
    assert stats["Canon"]["max_iso"] == 50

def test_group_push(db):
    # Group by Make, push Models
    pipeline = [
        {"$group": {"_id": "$Make", "models": {"$push": "$Model"}}}
    ]
    results = db.aggregate(pipeline)
    models = {r["_id"]: r["models"] for r in results}
    
    assert "iPhone 12" in models["Apple"]
    assert "iPhone 13" in models["Apple"]
    assert len(models["Apple"]) == 3
    assert "EOS R5" in models["Canon"]

def test_semantic_search_in_pipeline(db):
    # Match using "query" (semantic) -> Sort
    # Note: Semantic search results are mocked/approximate in this test env usually, 
    # but we check if the pipeline structure works.
    pipeline = [
        {"$match": {"query": "iphone"}},
        {"$limit": 1}
    ]
    results = db.aggregate(pipeline)
    assert len(results) == 1
    # Should have score and SourceFile
    assert "score" in results[0]
    assert "SourceFile" in results[0]

def test_empty_pipeline(db):
    assert db.aggregate([]) == []

def test_match_in_operator(db):
    pipeline = [
        {"$match": {"Make": {"$in": ["Sony", "Canon"]}}}
    ]
    results = db.aggregate(pipeline)
    # Sony (1) + Canon (2) = 3
    assert len(results) == 3

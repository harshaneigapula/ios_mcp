import chromadb
import os
import shutil
import pytest
from src.database import Database

# Setup temporary DB
DB_PATH = "./test_chroma_db_advanced"

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
    ]
    
    db_instance.upsert_files(metadata)
    yield db_instance
    
    # Cleanup
    if os.path.exists(DB_PATH):
        shutil.rmtree(DB_PATH)

def test_filter_only(db):
    results = db.advanced_query(where={"Make": "Apple"})
    assert len(results) == 3

def test_sort_asc(db):
    results = db.advanced_query(sort_by="ISO", sort_order="asc")
    isos = [r["ISO"] for r in results]
    assert isos == [50, 100, 100, 200, 800]

def test_sort_desc(db):
    results = db.advanced_query(sort_by="ISO", sort_order="desc")
    isos = [r["ISO"] for r in results]
    assert isos == [800, 200, 100, 100, 50]

def test_pagination(db):
    # Sort by ISO asc: 50, 100, 100, 200, 800
    # Limit 2, Offset 1 -> Should get [100, 100] (indices 1 and 2)
    results = db.advanced_query(sort_by="ISO", sort_order="asc", limit=2, offset=1)
    assert len(results) == 2
    assert results[0]["ISO"] == 100
    assert results[1]["ISO"] == 100

def test_projection(db):
    results = db.advanced_query(where={"Make": "Canon"}, projection=["Model"])
    assert len(results) == 1
    assert "Model" in results[0]
    assert "ISO" not in results[0]
    assert "SourceFile" in results[0] # Should be included by default

def test_semantic_search_sort(db):
    # Semantic search usually returns by relevance.
    # Here we force a sort by Date after semantic search.
    # Note: Since we use dummy embeddings, semantic search results might be arbitrary.
    # But the sort logic should still apply to the returned results.
    results = db.advanced_query(query="iphone", sort_by="CreationDate", sort_order="desc")
    dates = [r["CreationDate"] for r in results]
    # Check if dates are sorted descending
    assert dates == sorted(dates, reverse=True)

def test_complex_filter(db):
    # Apple AND ISO >= 100
    where = {
        "$and": [
            {"Make": "Apple"},
            {"ISO": {"$gte": 100}}
        ]
    }
    results = db.advanced_query(where=where)
    assert len(results) == 3 # All apples are >= 100

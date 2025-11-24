import chromadb
import os
import shutil
import pytest
from src.database import Database

# Setup temporary DB
DB_PATH = "./test_chroma_db_mixed"

@pytest.fixture(scope="module")
def db():
    if os.path.exists(DB_PATH):
        shutil.rmtree(DB_PATH)
    
    db_instance = Database(db_path=DB_PATH)
    
    # Insert test data with mixed types for the same field
    metadata = [
        {"SourceFile": "/tmp/1.jpg", "ISO": 100},      # int
        {"SourceFile": "/tmp/2.jpg", "ISO": "200"},    # str
        {"SourceFile": "/tmp/3.jpg", "ISO": 50.5},     # float
        {"SourceFile": "/tmp/4.jpg", "ISO": "invalid"} # str not convertible
    ]
    
    db_instance.upsert_files(metadata)
    yield db_instance
    
    # Cleanup
    if os.path.exists(DB_PATH):
        shutil.rmtree(DB_PATH)

def test_mixed_type_min_max(db):
    # This should fail with TypeError if not handled
    pipeline = [
        {"$group": {
            "_id": None, 
            "min_iso": {"$min": "$ISO"},
            "max_iso": {"$max": "$ISO"},
            "avg_iso": {"$avg": "$ISO"},
            "sum_iso": {"$sum": "$ISO"}
        }}
    ]
    results = db.aggregate(pipeline)
    
    # We expect the code to handle this gracefully, probably by converting to float where possible
    # 100, 200, 50.5 -> Min 50.5, Max 200, Sum 350.5, Avg 116.83
    # "invalid" should likely be ignored for numerical ops
    
    res = results[0]
    assert res["min_iso"] == 50.5
    assert res["max_iso"] == 200.0
    assert res["sum_iso"] == 350.5
    assert abs(res["avg_iso"] - 116.833) < 0.01

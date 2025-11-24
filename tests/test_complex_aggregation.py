import chromadb
import os
import shutil
import pytest
import json
from src.database import Database

# Setup temporary DB
DB_PATH = "./test_chroma_db_complex_agg"

@pytest.fixture(scope="module")
def db():
    if os.path.exists(DB_PATH):
        shutil.rmtree(DB_PATH)
    
    db_instance = Database(db_path=DB_PATH)
    
    # Insert test data with specific fields
    metadata = [
        {
            "SourceFile": "/tmp/1.jpg", 
            "EXIF:ISO": 100, 
            "EXIF:FNumber": 2.8, 
            "EXIF:ShutterSpeedValue": 0.01, 
            "Composite:Megapixels": 12.0
        },
        {
            "SourceFile": "/tmp/2.jpg", 
            "EXIF:ISO": 400, 
            "EXIF:FNumber": 5.6, 
            "EXIF:ShutterSpeedValue": 0.005, 
            "Composite:Megapixels": 24.0
        },
        {
            "SourceFile": "/tmp/3.jpg", 
            "EXIF:ISO": 200, 
            "EXIF:FNumber": 4.0, 
            "EXIF:ShutterSpeedValue": 0.02, 
            "Composite:Megapixels": 12.0
        },
    ]
    
    db_instance.upsert_files(metadata)
    yield db_instance
    
    # Cleanup
    if os.path.exists(DB_PATH):
        shutil.rmtree(DB_PATH)

def test_complex_aggregation(db):
    pipeline_json = '[{"$group": {"_id": null, "total_photos": {"$sum": 1}, "avg_iso": {"$avg": "$EXIF:ISO"}, "min_iso": {"$min": "$EXIF:ISO"}, "max_iso": {"$max": "$EXIF:ISO"}, "avg_aperture": {"$avg": "$EXIF:FNumber"}, "min_aperture": {"$min": "$EXIF:FNumber"}, "max_aperture": {"$max": "$EXIF:FNumber"}, "avg_shutter_speed": {"$avg": "$EXIF:ShutterSpeedValue"}, "min_shutter_speed": {"$min": "$EXIF:ShutterSpeedValue"}, "max_shutter_speed": {"$max": "$EXIF:ShutterSpeedValue"}, "avg_megapixels": {"$avg": "$Composite:Megapixels"}, "min_megapixels": {"$min": "$Composite:Megapixels"}, "max_megapixels": {"$max": "$Composite:Megapixels"}}}]'
    
    pipeline = json.loads(pipeline_json)
    results = db.aggregate(pipeline)
    
    assert len(results) == 1
    res = results[0]
    
    assert res["_id"] is None
    assert res["total_photos"] == 3
    
    # ISO: 100, 400, 200 -> Avg 233.33, Min 100, Max 400
    assert abs(res["avg_iso"] - 233.33) < 0.1
    assert res["min_iso"] == 100
    assert res["max_iso"] == 400
    
    # Aperture: 2.8, 5.6, 4.0 -> Avg 4.13, Min 2.8, Max 5.6
    assert abs(res["avg_aperture"] - 4.13) < 0.1
    assert res["min_aperture"] == 2.8
    assert res["max_aperture"] == 5.6
    
    # Megapixels: 12, 24, 12 -> Avg 16, Min 12, Max 24
    assert res["avg_megapixels"] == 16.0
    assert res["min_megapixels"] == 12.0
    assert res["max_megapixels"] == 24.0

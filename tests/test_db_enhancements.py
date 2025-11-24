import sys
import os
import json

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from database import Database

def test_db_enhancements():
    print("Testing Database Enhancements...")
    db = Database(db_path="/tmp/test_chroma_db")
    db.clear_db()
    
    # 1. Insert dummy data
    print("Inserting dummy data...")
    metadata_list = [
        {"SourceFile": "/tmp/1.jpg", "Model": "iPhone 12", "Type": "Image"},
        {"SourceFile": "/tmp/2.jpg", "Model": "iPhone 12", "Type": "Image"},
        {"SourceFile": "/tmp/3.png", "Model": "iPhone 13", "Type": "Image"},
        {"SourceFile": "/tmp/4.mp4", "Model": "iPhone 13", "Type": "Video"},
        {"SourceFile": "/tmp/5.txt", "Model": "Unknown", "Type": "Text"},
    ]
    db.upsert_files(metadata_list)
    
    # 2. Test count_files
    print("\nTesting count_files...")
    total = db.count_files()
    print(f"Total files: {total} (Expected: 5)")
    assert total == 5
    
    iphone12_count = db.count_files(where={"Model": "iPhone 12"})
    print(f"iPhone 12 count: {iphone12_count} (Expected: 2)")
    assert iphone12_count == 2
    
    # 3. Test group_files_by_field
    print("\nTesting group_files_by_field...")
    by_model = db.group_files_by_field("Model")
    print(f"Group by Model: {by_model}")
    assert by_model["iPhone 12"] == 2
    assert by_model["iPhone 13"] == 2
    assert by_model["Unknown"] == 1
    
    by_type = db.group_files_by_field("Type")
    print(f"Group by Type: {by_type}")
    assert by_type["Image"] == 3
    assert by_type["Video"] == 1
    
    # 4. Test get_database_stats
    print("\nTesting get_database_stats...")
    stats = db.get_database_stats()
    print(f"Stats: {stats}")
    assert stats["total_files"] == 5
    
    print("\nAll database tests passed!")

if __name__ == "__main__":
    test_db_enhancements()

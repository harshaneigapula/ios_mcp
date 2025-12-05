import os
import time
import shutil
from typing import List, Dict, Any
from unittest.mock import MagicMock, patch

# Mock dependencies
import sys
sys.path.append(os.getcwd()) # Add current directory to path
sys.modules['exiftool'] = MagicMock()
sys.modules['chromadb'] = MagicMock()
sys.modules['chromadb.config'] = MagicMock()

# Import the functions to test
from src.device import scan_photos

# Mock ExifToolHelper
mock_et = MagicMock()
sys.modules['exiftool'].ExifToolHelper.return_value.__enter__.return_value = mock_et

def create_dummy_files(directory: str, count: int):
    if os.path.exists(directory):
        shutil.rmtree(directory)
    os.makedirs(os.path.join(directory, "DCIM"))
    
    for i in range(count):
        with open(os.path.join(directory, "DCIM", f"img_{i}.jpg"), "w") as f:
            f.write("dummy content")

def test_parallel_scan():
    mount_point = "/tmp/test_mount"
    create_dummy_files(mount_point, 105) # 105 files to test chunking (50 per chunk -> 3 chunks)
    
    # Mock metadata return
    def get_metadata(files):
        time.sleep(0.1) # Simulate work
        return [{"SourceFile": f, "Model": "Test"} for f in files]
    
    mock_et.get_metadata.side_effect = get_metadata
    
    print("Starting scan...")
    start_time = time.time()
    
    callback_counts = []
    def callback(chunk):
        print(f"Callback received {len(chunk)} items")
        callback_counts.append(len(chunk))
        
    results = scan_photos(mount_point, callback=callback, max_workers=4)
    
    end_time = time.time()
    duration = end_time - start_time
    
    print(f"Scan completed in {duration:.2f} seconds")
    print(f"Total results: {len(results)}")
    print(f"Callback calls: {len(callback_counts)}")
    print(f"Callback chunk sizes: {callback_counts}")
    
    assert len(results) == 105
    assert len(callback_counts) >= 3 # Should be at least 3 chunks (50, 50, 5)
    assert sum(callback_counts) == 105
    
    print("Verification Successful!")

if __name__ == "__main__":
    test_parallel_scan()

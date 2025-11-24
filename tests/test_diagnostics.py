import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from server import check_db_status, check_mount_status

def test_diagnostics():
    print("Testing check_db_status...")
    db_status = check_db_status()
    print(f"DB Status: {db_status}")
    
    print("\nTesting check_mount_status...")
    mount_status = check_mount_status()
    print(f"Mount Status: {mount_status}")

if __name__ == "__main__":
    test_diagnostics()

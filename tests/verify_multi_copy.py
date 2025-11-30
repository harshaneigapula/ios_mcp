import sys
import os
from unittest.mock import MagicMock
import tempfile
import shutil

# Mock dependencies BEFORE importing server
sys.modules["mcp.server.fastmcp"] = MagicMock()
sys.modules["src.database"] = MagicMock()
sys.modules["database"] = MagicMock()
sys.modules["src.device"] = MagicMock()
sys.modules["device"] = MagicMock()

# Mock FastMCP class instance
mock_mcp_instance = MagicMock()
def mock_tool():
    def decorator(f):
        return f
    return decorator
mock_mcp_instance.tool = mock_tool
sys.modules["mcp.server.fastmcp"].FastMCP.return_value = mock_mcp_instance

# Add src to path
sys.path.append(os.path.abspath("src"))

# Import server
try:
    import server
except ImportError:
    sys.path.append(os.getcwd())
    import src.server as server

def test_multi_copy():
    print("Starting verification for multiple files...")
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup mock mount point
        mount_point = os.path.join(tmpdir, "mount")
        os.makedirs(mount_point)
        server.MOUNT_POINT = mount_point
        print(f"Mock Mount Point: {mount_point}")
        
        # Create source files
        files = ["file1.txt", "file2.txt", "file3.txt"]
        src_paths = []
        for f_name in files:
            p = os.path.join(mount_point, f_name)
            with open(p, "w") as f:
                f.write(f"Content of {f_name}")
            src_paths.append(p)
        print(f"Created source files: {src_paths}")
            
        # Destination
        dest_folder = os.path.join(tmpdir, "dest_folder")
        print(f"Destination Folder: {dest_folder}")
        
        # Call function
        print("Calling copy_files_to_local...")
        result = server.copy_files_to_local(src_paths, dest_folder)
        print(f"Result: {result}")
        
        # Verify
        success = True
        for f_name in files:
            dest_file = os.path.join(dest_folder, f_name)
            if os.path.exists(dest_file):
                with open(dest_file, "r") as f:
                    content = f.read()
                if content == f"Content of {f_name}":
                    print(f"SUCCESS: {f_name} copied correctly.")
                else:
                    print(f"FAILURE: {f_name} content mismatch.")
                    success = False
            else:
                print(f"FAILURE: {f_name} not found in destination.")
                success = False
                
        if success:
            print("ALL FILES COPIED SUCCESSFULLY.")

        # Test Partial Failure (One file missing)
        print("\nTesting Partial Failure...")
        bad_path = os.path.join(mount_point, "missing.txt")
        mixed_paths = [src_paths[0], bad_path]
        
        result = server.copy_files_to_local(mixed_paths, os.path.join(tmpdir, "dest_mixed"))
        print(f"Result: {result}")
        
        if "Copied 1/2 files" in result and "File not found" in result:
             print("SUCCESS: Partial failure reported correctly.")
        else:
             print("FAILURE: Partial failure report incorrect.")

if __name__ == "__main__":
    test_multi_copy()

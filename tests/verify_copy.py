import sys
import os
from unittest.mock import MagicMock
import tempfile
import shutil

# Mock dependencies BEFORE importing server
sys.modules["mcp.server.fastmcp"] = MagicMock()
# Mock both relative and absolute imports that might happen
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
    # If src is not a package, try importing directly if we are in root
    sys.path.append(os.getcwd())
    import src.server as server

def test_copy():
    print("Starting verification...")
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup mock mount point
        mount_point = os.path.join(tmpdir, "mount")
        os.makedirs(mount_point)
        # Override server's MOUNT_POINT
        server.MOUNT_POINT = mount_point
        print(f"Mock Mount Point: {mount_point}")
        
        # Create source file
        src_file = os.path.join(mount_point, "test.txt")
        with open(src_file, "w") as f:
            f.write("Hello World")
        print(f"Created source file: {src_file}")
            
        # Destination
        dest_file = os.path.join(tmpdir, "dest", "copied.txt")
        print(f"Destination: {dest_file}")
        
        # Call function
        print("Calling copy_files_to_local...")
        result = server.copy_files_to_local([src_file], dest_file)
        print(f"Result: {result}")
        
        # Verify
        if os.path.exists(dest_file):
            with open(dest_file, "r") as f:
                content = f.read()
            if content == "Hello World":
                print("SUCCESS: File copied correctly.")
            else:
                print(f"FAILURE: Content mismatch. Expected 'Hello World', got '{content}'")
        else:
            print("FAILURE: Destination file not found.")

        # Test Security Check
        print("\nTesting Security Check...")
        outside_file = os.path.join(tmpdir, "outside.txt")
        with open(outside_file, "w") as f:
            f.write("Secret")
        
        result = server.copy_files_to_local([outside_file], os.path.join(tmpdir, "dest", "stolen.txt"))
        print(f"Result: {result}")
        if "Access denied" in result:
             print("SUCCESS: Security check passed.")
        else:
             print("FAILURE: Security check failed.")

if __name__ == "__main__":
    test_copy()

import unittest
from unittest.mock import patch, MagicMock, mock_open
import sys
import os
import base64

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the function to test. 
# Note: Since read_image is decorated with @mcp.tool(), we might need to access the original function 
# or just import it. The FastMCP decorator usually keeps the original function accessible or wraps it.
# However, in server.py, 'read_image' is defined at module level.
# Let's import server to access it.
from src import server

class TestReadImage(unittest.TestCase):

    def setUp(self):
        # Ensure MOUNT_POINT matches what's in server.py for tests
        server.MOUNT_POINT = "/tmp/iphone"

    @patch('os.path.exists')
    @patch('subprocess.run')
    @patch('builtins.open', new_callable=mock_open, read_data=b'resized_image_data')
    @patch('os.remove')
    def test_read_standard_image(self, mock_remove, mock_file, mock_run, mock_exists):
        import json
        mock_exists.return_value = True
        
        # Mock subprocess.run for sips
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        
        file_path = "/tmp/iphone/DCIM/100APPLE/IMG_1234.JPG"
        result = server.read_image(file_path)
        
        # Parse JSON result
        data = json.loads(result)
        
        # Expect base64 encoded 'resized_image_data'
        expected_data = base64.b64encode(b'resized_image_data').decode('utf-8')
        
        self.assertEqual(data['type'], 'image')
        self.assertEqual(data['data'], expected_data)
        self.assertEqual(data['mimeType'], 'image/jpeg') # Always jpeg after resize
        
        # Verify sips was called with resize args
        args, _ = mock_run.call_args
        cmd = args[0]
        self.assertEqual(cmd[0], "sips")
        self.assertEqual(cmd[1], "-Z")
        self.assertEqual(cmd[2], "128")
        self.assertEqual(cmd[6], file_path)
        
        # Verify temp file was removed
        mock_remove.assert_called()

    @patch('os.path.exists')
    def test_file_not_found(self, mock_exists):
        mock_exists.return_value = False
        result = server.read_image("/tmp/iphone/missing.jpg")
        self.assertEqual(result, "File not found.")

    def test_access_denied(self):
        result = server.read_image("/etc/passwd")
        self.assertIn("Access denied", result)

    @patch('os.path.exists')
    @patch('subprocess.run')
    @patch('builtins.open', new_callable=mock_open, read_data=b'resized_heic_data')
    @patch('os.remove')
    def test_read_heic_image(self, mock_remove, mock_file, mock_run, mock_exists):
        import json
        mock_exists.return_value = True
        
        # Mock subprocess.run for sips
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        
        file_path = "/tmp/iphone/DCIM/100APPLE/IMG_5678.HEIC"
        result = server.read_image(file_path)
        
        # Parse JSON result
        data = json.loads(result)
        
        # Expect base64 encoded 'resized_heic_data'
        expected_data = base64.b64encode(b'resized_heic_data').decode('utf-8')
        
        self.assertEqual(data['type'], 'image')
        self.assertEqual(data['data'], expected_data)
        self.assertEqual(data['mimeType'], 'image/jpeg')
        
        # Verify sips was called with resize args
        args, _ = mock_run.call_args
        cmd = args[0]
        self.assertEqual(cmd[0], "sips")
        self.assertEqual(cmd[1], "-Z")
        self.assertEqual(cmd[2], "128")
        self.assertEqual(cmd[6], file_path)
        
        # Verify temp file was removed
        mock_remove.assert_called()

    @patch('os.path.exists')
    @patch('subprocess.run')
    def test_sips_failure(self, mock_run, mock_exists):
        mock_exists.return_value = True
        
        # Mock subprocess.run to fail
        mock_run.return_value = MagicMock(returncode=1, stderr="Sips failed")
        
        file_path = "/tmp/iphone/DCIM/100APPLE/broken.jpg"
        result = server.read_image(file_path)
        
        self.assertIn("Error processing image", result)

if __name__ == '__main__':
    unittest.main()

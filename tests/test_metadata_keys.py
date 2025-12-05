import unittest
import shutil
import tempfile
import os
import sys
import json

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from database import Database

class TestMetadataKeys(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db = Database(db_path=self.test_dir)
        
        # Insert some dummy data
        data = [
            {"SourceFile": "a.jpg", "EXIF:Model": "iPhone", "IPTC:Keywords": "test"},
            {"SourceFile": "b.jpg", "EXIF:ISO": 100, "General": "Info"},
            {"SourceFile": "c.jpg", "XMP:Title": "Title"}
        ]
        self.db.upsert_files(data)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_get_cached_keys_categories(self):
        # Should return categories
        keys = self.db.get_cached_keys()
        self.assertIn("EXIF", keys)
        self.assertIn("IPTC", keys)
        self.assertIn("XMP", keys)
        self.assertIn("General", keys)
        
        # Verify cache file exists
        self.assertTrue(os.path.exists(self.db.cache_path))

    def test_get_cached_keys_filter(self):
        # Filter by EXIF
        keys = self.db.get_cached_keys(category="EXIF")
        self.assertIn("EXIF:Model", keys)
        self.assertIn("EXIF:ISO", keys)
        self.assertNotIn("IPTC:Keywords", keys)
        
        # Filter by EXIF: (with colon)
        keys2 = self.db.get_cached_keys(category="EXIF:")
        self.assertEqual(keys, keys2)

    def test_refresh_cache(self):
        # Populate cache first
        self.db.get_cached_keys()
        
        # Add new data
        new_data = [{"SourceFile": "d.jpg", "NewCat:Key": "Value"}]
        self.db.upsert_files(new_data)
        
        # Without refresh, should not see NewCat (because it's reading from stale cache)
        keys = self.db.get_cached_keys()
        self.assertNotIn("NewCat", keys)
        
        # With refresh, should see NewCat
        keys = self.db.get_cached_keys(refresh=True)
        self.assertIn("NewCat", keys)

    def test_get_metadata_categories_tool(self):
        # This tests the underlying DB logic which the tool uses
        # The tool itself just calls db.get_cached_keys(category=None)
        keys = self.db.get_cached_keys(category=None)
        self.assertIn("EXIF", keys)
        self.assertIn("IPTC", keys)

    def test_get_all_keys_uses_cache(self):
        # Ensure cache exists
        self.db.update_keys_cache()
        
        # Modify cache manually to prove it's being used
        with open(self.db.cache_path, 'w') as f:
            json.dump(["Fake:Key"], f)
            
        # get_all_keys should return the fake key
        keys = self.db.get_all_keys()
        self.assertIn("Fake:Key", keys)
        self.assertNotIn("EXIF:Model", keys)
        
        # Restore cache
        self.db.update_keys_cache()

    def test_find_similar_keys(self):
        # Should find similar keys
        matches = self.db.find_similar_keys("Model")
        # "EXIF:Model" should be a match
        self.assertTrue(any("Model" in m for m in matches))
        
        # Verify it uses cache (indirectly via get_all_keys)
        # Modify cache manually
        with open(self.db.cache_path, 'w') as f:
            json.dump(["Fake:Model"], f)
            
        matches = self.db.find_similar_keys("Model")
        self.assertIn("Fake:Model", matches)
        
        # Restore cache
        self.db.update_keys_cache()

if __name__ == '__main__':
    unittest.main()

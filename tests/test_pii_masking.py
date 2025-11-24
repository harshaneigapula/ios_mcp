import unittest
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.device import mask_pii, PII_FIELDS

class TestPIIMasking(unittest.TestCase):

    def test_mask_pii(self):
        # Create a dummy device info dictionary with some PII and some non-PII fields
        info = {
            "DeviceName": "My iPhone",
            "ProductType": "iPhone13,2",
            "UniqueDeviceID": "00008101-001E30590A0A001E",
            "SerialNumber": "F2LXYZ123ABC",
            "WiFiAddress": "00:11:22:33:44:55",
            "SafeField": "SafeValue"
        }
        
        masked = mask_pii(info)
        
        # Check that PII fields are redacted
        self.assertEqual(masked["UniqueDeviceID"], "REDACTED")
        self.assertEqual(masked["SerialNumber"], "REDACTED")
        self.assertEqual(masked["WiFiAddress"], "REDACTED")
        
        # Check that non-PII fields are preserved
        self.assertEqual(masked["DeviceName"], "My iPhone")
        self.assertEqual(masked["ProductType"], "iPhone13,2")
        self.assertEqual(masked["SafeField"], "SafeValue")
        
        # Check that original dictionary is not modified
        self.assertNotEqual(info["UniqueDeviceID"], "REDACTED")

    def test_all_pii_fields(self):
        # Ensure all fields in PII_FIELDS are actually masked
        info = {field: "secret" for field in PII_FIELDS}
        masked = mask_pii(info)
        
        for field in PII_FIELDS:
            self.assertEqual(masked[field], "REDACTED", f"Field {field} was not masked")

    def test_nested_masking(self):
        # Test recursive masking
        info = {
            "DeviceName": "My iPhone",
            "BasebandKeyHashInformation": {
                "SKeyHash": "secret_hash",
                "OtherField": "safe"
            },
            "CarrierBundleInfoArray": [
                {
                    "IntegratedCircuitCardIdentity": "secret_iccid",
                    "MCC": "310"
                },
                {
                    "GID1": "secret_gid",
                    "Slot": "1"
                }
            ]
        }
        
        masked = mask_pii(info)
        
        # Check nested dict
        self.assertEqual(masked["BasebandKeyHashInformation"]["SKeyHash"], "REDACTED")
        self.assertEqual(masked["BasebandKeyHashInformation"]["OtherField"], "safe")
        
        # Check list of dicts
        self.assertEqual(masked["CarrierBundleInfoArray"][0]["IntegratedCircuitCardIdentity"], "REDACTED")
        self.assertEqual(masked["CarrierBundleInfoArray"][0]["MCC"], "310")
        self.assertEqual(masked["CarrierBundleInfoArray"][1]["GID1"], "REDACTED")
        self.assertEqual(masked["CarrierBundleInfoArray"][1]["Slot"], "1")

if __name__ == '__main__':
    unittest.main()

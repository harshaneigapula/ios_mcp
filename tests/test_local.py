import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.device import get_devices, get_device_info, mount_device, unmount_device, scan_photos
from src.database import Database

def main():
    print("--- Testing Device Access ---")
    rc, out, err = get_devices()
    print(f"Devices: {out}")
    if rc != 0:
        print(f"Error listing devices: {err}")
        return

    if not out:
        print("No devices found. Connect an iPhone.")
        return

    udid = out.splitlines()[0].split()[0] # Assuming first word is UDID
    print(f"Using Device: {udid}")

    print("\n--- Testing Device Info ---")
    rc, info, err = get_device_info(udid)
    if rc == 0:
        print(f"Device Name: {info.get('DeviceName', 'Unknown')}")
        print(f"Product Type: {info.get('ProductType', 'Unknown')}")
    else:
        print(f"Error getting info: {err}")

    print("\n--- Testing Mount ---")
    mount_point = "/tmp/iphone_mount"
    success, msg = mount_device(mount_point)
    print(f"Mount Result: {msg}")
    
    if success:
        print("\n--- Testing Scan (Dry Run) ---")
        # We won't scan everything to avoid taking too long, just check if DCIM exists
        mount_point = "/tmp/iphone_mount"
        dcim = os.path.join(mount_point, "DCIM")
        if os.path.exists(dcim):
            print(f"DCIM found at {dcim}")
            # Uncomment to actually scan
            # metadata = scan_photos(mount_point)
            # print(f"Found {len(metadata)} photos")
            
            # Test Database
            print("\n--- Testing Database ---")
            db = Database()
            # db.upsert_files(metadata)
            all_files = db.get_all_files()
            print(f"Total files in DB: {len(all_files)}")
            
        else:
            print("DCIM not found.")

        print("\n--- Testing Unmount ---")
        success, msg = unmount_device(mount_point)
        print(f"Unmount Result: {msg}")

if __name__ == "__main__":
    main()

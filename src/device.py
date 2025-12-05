import subprocess
import json
import os
import xml.etree.ElementTree as ET
from typing import Tuple, List, Dict, Any, Optional
import exiftool

def run_cmd(cmd: list) -> Tuple[int, str, str]:
    """
    Run a shell command and return (exit_code, stdout, stderr).
    """
    try:
        p = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except Exception as e:
        return -1, "", str(e)

def get_devices() -> Tuple[int, str, str]:
    return run_cmd(["idevice_id", "-l"])

def parse_plist(elem: ET.Element) -> Any:
    tag = elem.tag

    if tag == "dict":
        items = list(elem)
        result = {}
        i = 0
        while i < len(items):
            key = items[i].text
            value = parse_plist(items[i + 1])
            result[key] = value
            i += 2
        return result

    if tag == "array":
        return [parse_plist(child) for child in elem]

    if tag == "string":
        return elem.text or ""

    if tag == "integer":
        return int(elem.text)

    if tag == "real":
        return float(elem.text)

    if tag == "true":
        return True

    if tag == "false":
        return False

    if tag == "data":
        return (elem.text or "").strip()

    return None

    return None

PII_FIELDS = {
    "UniqueDeviceID",
    "SerialNumber",
    "WiFiAddress",
    "BluetoothAddress",
    "EthernetAddress",
    "InternationalMobileEquipmentIdentity",
    "InternationalMobileEquipmentIdentity2",
    "MobileEquipmentIdentifier",
    "PhoneNumber",
    "IntegratedCircuitCardIdentity",
    "IntegratedCircuitCardIdentity2",
    "InternationalMobileSubscriberIdentity",
    "InternationalMobileSubscriberIdentity2",
    "MLBSerialNumber",
    "DieID",
    "BasebandSerialNumber",
    "ChipSerialNo",
    "WirelessBoardSerialNumber",
    "UniqueChipID",
    "PkHash",
    "BasebandMasterKeyHash",
    "MobileSubscriberCountryCode",
    "MobileSubscriberNetworkCode",
    "SKeyHash",
    "BootSessionID",
    "GID1",
    "GID2",
    "SIMGID1",
    "SIMGID2",
    "fm-account-masked",
    "fm-spkeys",
    "BasebandCertId",
    "BasebandChipID",
    "CertID",
    "ChipID"
}

def mask_pii(data: Any) -> Any:
    """
    Recursively mask PII fields in the device info.
    Handles dictionaries and lists.
    """
    if isinstance(data, dict):
        masked_dict = {}
        for key, value in data.items():
            if key in PII_FIELDS:
                masked_dict[key] = "REDACTED"
            else:
                masked_dict[key] = mask_pii(value)
        return masked_dict
    
    elif isinstance(data, list):
        return [mask_pii(item) for item in data]
        
    else:
        return data

def get_device_info(udid: str) -> Tuple[int, Dict[str, Any], str]:
    rc, xml_string, err = run_cmd(["ideviceinfo", "-u", udid, "-x"])
    if rc != 0:
        return rc, {}, err
        
    xml_string = xml_string.strip()
    if not xml_string.startswith("<?xml"):
        xml_string = xml_string.splitlines()
        xml_string = "\n".join(line for line in xml_string if line.strip().startswith("<"))

    try:
        root = ET.fromstring(xml_string)
        # Apple's plist XML usually has <plist> then <dict>
        if root.tag == 'plist':
            plist_dict = parse_plist(root[0])
        else:
            plist_dict = parse_plist(root)
            
        # Mask PII
        plist_dict = mask_pii(plist_dict)
        
        return rc, plist_dict, err
    except Exception as e:
        return -1, {}, f"Failed to parse plist: {e}"

def mount_device(mount_point: str) -> Tuple[bool, str]:
    
    if os.path.ismount(mount_point):
        print(True, "Already mounted")
        return True, "Already mounted"
    
    if os.path.isfile(mount_point):
        os.remove(mount_point)

    if os.path.isdir(mount_point):
        os.rmdir(mount_point)

    os.makedirs(mount_point, exist_ok=True)
    
    rc, out, err = run_cmd(["ifuse", mount_point])
    if rc == 0:
        return True, "Mounting Success"
    else:
        return False, f"Mounting Failed: {err}"

def unmount_device(mount_point: str) -> Tuple[bool, str]:
    if not os.path.ismount(mount_point):
        return True, "Not mounted"
        
    rc, out, err = run_cmd(["umount", mount_point])
    if rc == 0:
        return True, "Unmount Success"
    else:
        # Try diskutil on mac if umount fails
        rc, out, err = run_cmd(["diskutil", "unmount", mount_point])
        if rc == 0:
            return True, "Unmount Success (diskutil)"
        return False, f"Unmount Failed: {err}"

def process_chunk(chunk: List[str]) -> List[Dict[str, Any]]:
    """
    Helper to process a single chunk of files with ExifTool.
    """
    try:
        with exiftool.ExifToolHelper(check_execute=False) as et:
            return et.get_metadata(chunk)
    except Exception as e:
        print(f"Error processing chunk: {e}")
        return []

def scan_photos(mount_point: str, existing_files: set = None, callback: Optional[Any] = None, max_workers: int = 4) -> List[Dict[str, Any]]:
    """
    Scans for photos and extracts metadata.
    
    Args:
        mount_point: Path to the mounted device.
        existing_files: Set of file paths to skip.
        callback: Optional function to call with each chunk of metadata (List[Dict]).
        max_workers: Number of parallel workers for EXIF extraction.
    """
    import concurrent.futures
    
    dcim_path = os.path.join(mount_point, "DCIM")
    all_paths = []
    
    if not os.path.exists(dcim_path):
        print(f"DCIM not found at {dcim_path}")
        return []

    for root, dirs, files in os.walk(dcim_path):
        # print(root, len(files)) # Reduce noise
        for f in files:
            lower_f = f.lower()
            if lower_f.endswith(('.jpg', '.jpeg', '.png', '.heic', '.mov', '.mp4')):
                full_path = os.path.join(root, f)
                # Optimization: Skip if already in DB
                if existing_files and full_path in existing_files:
                    continue
                all_paths.append(full_path)
    
    if not all_paths:
        return []

    metadata_list = []
    chunk_size = 50 # Smaller chunk size for better parallelism with threads
    chunks = [all_paths[i:i + chunk_size] for i in range(0, len(all_paths), chunk_size)]
    
    print(f"Processing {len(all_paths)} files in {len(chunks)} chunks with {max_workers} workers...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all chunks
        future_to_chunk = {executor.submit(process_chunk, chunk): chunk for chunk in chunks}
        
        for future in concurrent.futures.as_completed(future_to_chunk):
            try:
                data = future.result()
                if data:
                    if callback:
                        callback(data)
                    metadata_list.extend(data)
            except Exception as e:
                print(f"Chunk processing failed: {e}")
        
    return metadata_list

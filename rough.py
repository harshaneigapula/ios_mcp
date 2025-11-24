import subprocess
import json
from typing import Tuple
import os
import exiftool
import xml.etree.ElementTree as ET


def run_cmd(cmd: list) -> Tuple[int, str, str]:
    """
    Run a shell command and return (exit_code, stdout, stderr).
    """
    p = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    return p.returncode, p.stdout.strip(), p.stderr.strip()

def get_devices():
    rc, out, err = run_cmd(["idevice_id", "-l"])
    return rc, out, err



def parse_plist(elem):
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


def plist_xml_to_json(xml_string, indent=2):
    # Remove any leading text like "Return code: 0"
    xml_string = xml_string.strip()
    if not xml_string.startswith("<?xml"):
        xml_string = xml_string.splitlines()
        xml_string = "\n".join(line for line in xml_string if line.strip().startswith("<"))

    root = ET.fromstring(xml_string)
    # Apple's plist XML usually has <plist> then <dict>
    plist_dict = parse_plist(root[0])
    return json.dumps(plist_dict, indent=indent)


def get_device_info(udid):
    rc, xml_string, err = run_cmd(["ideviceinfo", "-u", udid, "-x"])
    xml_string = xml_string.strip()
    if not xml_string.startswith("<?xml"):
        xml_string = xml_string.splitlines()
        xml_string = "\n".join(line for line in xml_string if line.strip().startswith("<"))

    root = ET.fromstring(xml_string)
    plist_dict = parse_plist(root[0])
    return rc, plist_dict, err


def mount_phone():
    mount_point = "/tmp/iphone_mount"
    os.makedirs(mount_point, exist_ok=True)
    rc = subprocess.call(["ifuse", mount_point])
    if rc == 0:
        return "Mounting Success"
    else:
        return "Mounting Not Success. Returned code: {}".format(rc)

def save_all_photo_to_db():
    mount_point = "/tmp/iphone_mount"
    dcim_path = os.path.join(mount_point, "DCIM")
    all_paths = []
    if os.path.exists(dcim_path):
        for root, dirs, files in os.walk(dcim_path):
            all_paths = all_paths + [os.path.join(root, f) for f in files]
    else:
        print("DCIM not found. Some iOS versions expose limited folders.")
    
    if len(all_paths) > 0:
        with exiftool.ExifToolHelper() as et:
            metadata = et.get_metadata(all_paths)

    # Need to save these in Database. 

def query_photos(query_params, select_params):

    build_query = #need to build this.
    data = #execute query on the build.

    return data
    
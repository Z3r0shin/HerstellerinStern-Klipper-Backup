#!/usr/bin/env python3

import urllib.request
import json
import time
import os
import re
import logging
from PIL import Image, ImageFilter, ImageEnhance
from pyzbar.pyzbar import decode

SNAPSHOT_URL = "http://127.0.0.1:1984/api/frame.jpeg?src=wyze_v3"
MOONRAKER_URL    = "http://127.0.0.1:7125"
SNAPSHOT_FILE    = "/tmp/spoolman_scan.jpg"
RESULT_FILE      = "/tmp/spoolman_last_scan.txt"
TIMEOUT          = 15
SCAN_INTERVAL    = 1.0

def write_result(msg):
    with open(RESULT_FILE, "w") as f:
        f.write(msg)
    print(msg)

def grab_snapshot():
    try:
        urllib.request.urlretrieve(SNAPSHOT_URL, SNAPSHOT_FILE)
        return os.path.getsize(SNAPSHOT_FILE) > 1000
    except Exception as e:
        write_result(f"ERROR: Snapshot failed: {e}")
        return False

def preprocess(image):
    variants = []
    img = image.convert("L")
    variants.append(ImageEnhance.Contrast(img).enhance(2.0))
    img2 = img.filter(ImageFilter.SHARPEN)
    img2 = ImageEnhance.Contrast(img2).enhance(2.0)
    variants.append(img2)
    return variants

def decode_qr():
    try:
        image = Image.open(SNAPSHOT_FILE)
        results = decode(image)
        if results:
            return results[0].data.decode("utf-8").strip()
        for variant in preprocess(image):
            results = decode(variant)
            if results:
                return results[0].data.decode("utf-8").strip()
        return ""
    except Exception as e:
        write_result(f"ERROR: Decode failed: {e}")
        return ""

def set_spool(spool_id):
    payload = json.dumps({"spool_id": spool_id}).encode()
    req = urllib.request.Request(
        f"{MOONRAKER_URL}/server/spoolman/spool_id",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception as e:
        write_result(f"ERROR: Moonraker call failed: {e}")
        return False

def main():
    write_result("Scanning... hold QR code up to camera")
    deadline = time.time() + TIMEOUT

    while time.time() < deadline:
        remaining = int(deadline - time.time())
        print(f"Scanning... {remaining}s remaining")

        if grab_snapshot():
            qr_data = decode_qr()
            if qr_data:
                match = re.search(r'web\+spoolman:s-(\d+)', qr_data, re.IGNORECASE)
                if match:
                    spool_id = int(match.group(1))
                    if set_spool(spool_id):
                        write_result(f"OK: Spool {spool_id} set as active")
                        return
                    else:
                        write_result(f"ERROR: Moonraker rejected spool {spool_id}")
                        return
                else:
                    write_result(f"ERROR: Not a Spoolman QR code: {qr_data}")
                    return

        time.sleep(SCAN_INTERVAL)

    write_result("ERROR: Timeout — no QR code detected in 15 seconds")

if __name__ == "__main__":
    main()

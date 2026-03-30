#!/usr/bin/env python3

import urllib.request
import urllib.error
import json
import time
import os
import re
import logging
from PIL import Image, ImageFilter, ImageEnhance
from pyzbar.pyzbar import decode

SNAPSHOT_URL     = "http://127.0.0.1:1984/api/frame.jpeg?src=wyze_v3"
MOONRAKER_URL    = "http://127.0.0.1:7125"
SNAPSHOT_FILE    = "/tmp/spoolman_scan.jpg"
RESULT_FILE      = "/tmp/spoolman_last_scan.txt"
SCAN_INTERVAL    = 1.0
SUCCESS_COOLDOWN = 10.0
LOG_FILE         = "/tmp/spoolman_scanner.log"

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s"
)

def write_result(msg):
    with open(RESULT_FILE, "w") as f:
        f.write(msg)
    logging.info(msg)

def grab_snapshot():
    try:
        urllib.request.urlretrieve(SNAPSHOT_URL, SNAPSHOT_FILE)
        size = os.path.getsize(SNAPSHOT_FILE)
        logging.debug(f"Snapshot grabbed: {size} bytes")
        return size > 1000
    except Exception as e:
        logging.warning(f"Snapshot failed: {e}")
        return False

def preprocess(image):
    variants = []
    img = image.convert("L")
    img = img.resize((img.width * 2, img.height * 2), Image.LANCZOS)
    img = img.filter(ImageFilter.SHARPEN)
    img = img.filter(ImageFilter.SHARPEN)
    img = ImageEnhance.Contrast(img).enhance(2.0)
    variants.append(img)
    img2 = img.filter(ImageFilter.EDGE_ENHANCE_MORE)
    variants.append(img2)
    img3 = image.convert("L")
    img3 = ImageEnhance.Contrast(img3).enhance(2.5)
    variants.append(img3)
    return variants

def decode_qr():
    try:
        image = Image.open(SNAPSHOT_FILE)
        variants = preprocess(image)
        for i, variant in enumerate(variants):
            results = decode(variant)
            if results:
                data = results[0].data.decode("utf-8").strip()
                logging.debug(f"QR decoded on variant {i}: {data}")
                return data
        logging.debug("No QR code found in any variant")
        return ""
    except Exception as e:
        logging.warning(f"Decode failed: {e}")
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
        logging.error(f"Moonraker call failed: {e}")
        return False

def main():
    logging.info("Spoolman scanner daemon started (HerstellerinStern)")
    write_result("Scanner ready")
    last_spool_id = None

    while True:
        if grab_snapshot():
            qr_data = decode_qr()
            if qr_data:
                match = re.search(r'web\+spoolman:s-(\d+)', qr_data, re.IGNORECASE)
                if match:
                    spool_id = int(match.group(1))
                    if spool_id != last_spool_id:
                        if set_spool(spool_id):
                            msg = f"OK: Spool {spool_id} set as active"
                            write_result(msg)
                            last_spool_id = spool_id
                            time.sleep(SUCCESS_COOLDOWN)
                            last_spool_id = None
                            continue
                        else:
                            write_result(f"ERROR: Moonraker rejected spool {spool_id}")
        time.sleep(SCAN_INTERVAL)

if __name__ == "__main__":
    main()

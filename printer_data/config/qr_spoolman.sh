#!/bin/bash

SNAPSHOT_URL="http://127.0.0.1:1984/api/frame.jpeg?src=wyze_v3"
SNAPSHOT_FILE="/tmp/spoolman_qr.jpg"
MOONRAKER_URL="http://127.0.0.1:7125"

wget -q "$SNAPSHOT_URL" -O "$SNAPSHOT_FILE"

if [ ! -f "$SNAPSHOT_FILE" ]; then
    echo "ERROR: Could not capture snapshot from go2rtc"
    exit 1
fi

QR_DATA=$(zbarimg --quiet --raw "$SNAPSHOT_FILE" 2>/dev/null)

if [ -z "$QR_DATA" ]; then
    echo "ERROR: No QR code detected in frame"
    rm -f "$SNAPSHOT_FILE"
    exit 1
fi

echo "QR data found: $QR_DATA"

SPOOL_ID=$(echo "$QR_DATA" | grep -oP 'web\+spoolman:s-\K[0-9]+')

if [ -z "$SPOOL_ID" ]; then
    echo "ERROR: Not a valid Spoolman QR code: $QR_DATA"
    rm -f "$SNAPSHOT_FILE"
    exit 1
fi

echo "Setting active spool ID: $SPOOL_ID"

RESULT=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST \
    -H "Content-Type: application/json" \
    -d "{\"spool_id\": $SPOOL_ID}" \
    "$MOONRAKER_URL/server/spoolman/spool_id")

if [ "$RESULT" = "200" ]; then
    echo "SUCCESS: Spool $SPOOL_ID is now active"
else
    echo "ERROR: Moonraker returned HTTP $RESULT"
fi

rm -f "$SNAPSHOT_FILE"

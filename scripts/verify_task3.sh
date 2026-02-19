#!/bin/bash
echo "=== Verifying Task 3: Caching & CDN ==="

# 1. Trigger report generation to cache it in S3
echo "Triggering report generation (First request)..."
curl -s http://localhost:8001/reports/user1 > /dev/null

# 2. Request again to get the CDN URL
echo "Getting CDN URL..."
RESPONSE=$(curl -s http://localhost:8001/reports/user1)
echo "API Response: $RESPONSE"

URL=$(echo "$RESPONSE" | grep -o '"report_url": *"[^"]*"' | cut -d'"' -f4)

if [ -z "$URL" ]; then
    echo "FAIL: No report_url found in response."
    exit 1
fi

echo "Found CDN URL: $URL"

# 3. Fetch from CDN
echo "Fetching from CDN..."
CDN_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$URL")

if [ "$CDN_STATUS" == "200" ]; then
    echo "SUCCESS: Report fetched from CDN."
else
    echo "FAIL: Could not fetch from CDN (Status: $CDN_STATUS)."
    echo "Note: Ensure Nginx is running on port 9090."
fi

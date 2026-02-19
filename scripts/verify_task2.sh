#!/bin/bash
echo "=== Verifying Task 2: Reports Service ==="

# We need to simulate a request.
# Since the API is protected by BFF (which requires a valid session),
# calling reports-service directly (port 8001) is the easiest way to check the internal logic
# IF the internal logic doesn't strictly validate the header (it usually doesn't in internal mesh).
# Reports Service is at localhost:8001

echo "Requesting report for user1 from Reports Service..."
RESPONSE=$(curl -s http://localhost:8001/reports/user1)

echo "Response:"
echo "$RESPONSE"

if [[ "$RESPONSE" == *"user_id"* ]]; then
    echo "SUCCESS: Received report data."
else
    echo "FAIL: Unexpected response."
fi

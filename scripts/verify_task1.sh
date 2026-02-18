#!/bin/bash
echo "=== Verifying Task 1: Security & BFF ==="

# Check if BFF is running
echo "Checking BFF Service health..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/docs)
if [ "$STATUS" == "200" ]; then
    echo "SUCCESS: BFF Service is accessible at http://localhost:8000"
else
    echo "FAIL: BFF Service returned $STATUS"
fi

# Check if Keycloak is reachable via BFF redirect (indirectly)
echo "Checking Keycloak reachability..."
STATUS_KC=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080)
if [ "$STATUS_KC" == "200" ]; then
    echo "SUCCESS: Keycloak is running."
else
    echo "FAIL: Keycloak is not accessible."
fi

echo "To fully verify Task 1, open http://localhost:3000 in your browser and try to Login."

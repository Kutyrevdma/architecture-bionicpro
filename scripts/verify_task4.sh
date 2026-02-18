#!/bin/bash
echo "=== Verifying Task 4: CDC (Debezium -> ClickHouse) ==="

NEW_USER="user_$(date +%s)"
echo "Inserting new user '$NEW_USER' into Postgres (CRM)..."

docker-compose exec -T source_db psql -U user -d source_db -c "
INSERT INTO crm_users (id, name, email, contract_date, model)
VALUES ('$NEW_USER', 'Auto User', 'auto@example.com', '2023-10-27', 'CyberArm-Z');
"

echo "Waiting for replication (approx 5-10 seconds)..."
sleep 10

echo "Checking ClickHouse for new user..."
# Query the Replicated Table directly to verify CDC
RESULT=$(docker-compose exec -T clickhouse clickhouse-client --query "
SELECT id, name, model FROM bionicpro.crm_users_replicated WHERE id = '$NEW_USER'
")

if [[ "$RESULT" == *"$NEW_USER"* ]]; then
    echo "SUCCESS: User '$NEW_USER' found in ClickHouse!"
    echo "Data: $RESULT"
else
    echo "FAIL: User '$NEW_USER' not found in ClickHouse."
    echo "Debug: Check Debezium status at http://localhost:8083/connectors/crm-connector/status"
fi

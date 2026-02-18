#!/bin/bash
set -e

echo "=== Starting BionicPRO Project ==="

# 1. Start Docker Containers
echo "Building and starting services..."
docker-compose up -d --build

# 2. Wait for Services
echo "Waiting for services to initialize..."

# Wait for Postgres (Source DB)
echo "Waiting for Source DB..."
until docker-compose exec source_db pg_isready -U user; do
  sleep 2
done

# Wait for ClickHouse
echo "Waiting for ClickHouse..."
until docker-compose exec clickhouse clickhouse-client --query "SELECT 1"; do
  sleep 2
done

# Wait for Kafka Connect (Debezium)
echo "Waiting for Debezium..."
until curl -s -o /dev/null -w "%{http_code}" http://localhost:8083/connectors/; do
  sleep 5
done

# 3. Initialize Databases
echo "Initializing Databases..."
bash scripts/init_db.sh

# 4. Register CDC Connector
echo "Registering CDC Connector..."
bash scripts/register_connector.sh

echo "=== Project Started Successfully ==="
echo "You can now run verify scripts."

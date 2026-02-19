import psycopg2
import os
import random
from datetime import datetime, timedelta

# Configuration (matching docker-compose)
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5434")
DB_NAME = os.getenv("DB_NAME", "source_db")
DB_USER = os.getenv("DB_USER", "user")
DB_PASS = os.getenv("DB_PASS", "password")

def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )

def seed_crm(cursor):
    print("Seeding CRM data...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS crm_users (
            id VARCHAR(50) PRIMARY KEY,
            name VARCHAR(100),
            email VARCHAR(100),
            contract_date DATE,
            model VARCHAR(50)
        );
    """)

    users = [
        ("user1", "User One", "user1@example.com", "2023-01-15", "Hand-X1"),
        ("user2", "User Two", "user2@example.com", "2023-02-20", "Leg-Y2"),
        ("admin1", "Admin One", "admin1@example.com", "2023-03-01", "Hand-Z3")
    ]

    for uid, name, email, date, model in users:
        cursor.execute(
            "INSERT INTO crm_users (id, name, email, contract_date, model) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
            (uid, name, email, date, model)
        )

def seed_telemetry(cursor):
    print("Seeding Telemetry data...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS telemetry_logs (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(50),
            timestamp TIMESTAMP,
            signal_strength INT,
            battery_level INT,
            action VARCHAR(50)
        );
    """)

    user_ids = ["user1", "user2"]
    actions = ["grip", "release", "rotate_left", "rotate_right", "idle"]

    # Generate data for last 7 days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)

    # Simple batch insert logic
    current = start_date
    while current < end_date:
        for uid in user_ids:
            # 5-10 logs per hour per user
            for _ in range(random.randint(5, 10)):
                log_time = current + timedelta(minutes=random.randint(0, 59))
                signal = random.randint(50, 100)
                battery = max(0, 100 - (log_time - start_date).days * 10) # Drains over days
                action = random.choice(actions)

                cursor.execute(
                    "INSERT INTO telemetry_logs (user_id, timestamp, signal_strength, battery_level, action) VALUES (%s, %s, %s, %s, %s)",
                    (uid, log_time, signal, battery, action)
                )
        current += timedelta(hours=1)

def main():
    try:
        conn = get_connection()
        conn.autocommit = True
        cursor = conn.cursor()

        seed_crm(cursor)
        seed_telemetry(cursor)

        print("Seeding complete.")
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error seeding data: {e}")

if __name__ == "__main__":
    main()

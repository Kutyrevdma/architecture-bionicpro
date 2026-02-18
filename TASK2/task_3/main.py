from fastapi import FastAPI, HTTPException, Request
from clickhouse_driver import Client
import os

app = FastAPI()

CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "clickhouse")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", 9000))

def get_clickhouse_client():
    return Client(host=CLICKHOUSE_HOST, port=CLICKHOUSE_PORT)

@app.get("/reports/{user_id}")
def get_user_report(user_id: str, request: Request):
    # Security check: Ideally, we verify a token or a signature from the BFF.
    # For now, we assume the network is private and the BFF has done the auth check.
    # In a real microservices mesh (Istio), this would be mTLS/JWT verified.

    # Simple check: Ensure user_id matches X-User-ID header if passed by BFF (optional hardening)
    # authenticated_user = request.headers.get("X-User-ID")
    # if authenticated_user and authenticated_user != user_id:
    #     raise HTTPException(status_code=403, detail="Forbidden")

    try:
        client = get_clickhouse_client()
        # Query OLAP
        result = client.execute(
            """
            SELECT report_date, avg_signal, min_battery, total_actions
            FROM bionicpro.user_daily_reports
            WHERE user_id = %(user_id)s
            ORDER BY report_date DESC
            """,
            {'user_id': user_id}
        )

        if not result:
            return {"message": "No reports found for this user."}

        # Format
        reports = []
        for row in result:
            reports.append({
                "date": row[0],
                "avg_signal": row[1],
                "min_battery": row[2],
                "total_actions": row[3]
            })

        return {"user_id": user_id, "reports": reports}

    except Exception as e:
        print(f"Error querying ClickHouse: {e}")
        # Return 500 or empty if DB not ready
        raise HTTPException(status_code=500, detail="Error retrieving reports")

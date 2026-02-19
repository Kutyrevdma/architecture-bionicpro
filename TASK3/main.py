from fastapi import FastAPI, HTTPException, Request
from clickhouse_driver import Client
import boto3
from botocore.client import Config
import os
import json
from datetime import datetime

app = FastAPI()

CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "clickhouse")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", 9000))

S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://minio:9000")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "minioadmin")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "minioadmin")
S3_BUCKET = os.getenv("S3_BUCKET", "reports")
CDN_URL = os.getenv("CDN_URL", "http://localhost:9090")

def get_clickhouse_client():
    return Client(host=CLICKHOUSE_HOST, port=CLICKHOUSE_PORT)

def get_s3_client():
    return boto3.client('s3',
                        endpoint_url=S3_ENDPOINT,
                        aws_access_key_id=S3_ACCESS_KEY,
                        aws_secret_access_key=S3_SECRET_KEY,
                        config=Config(signature_version='s3v4'),
                        region_name='us-east-1')

@app.get("/reports/{user_id}")
def get_user_report(user_id: str, request: Request):

    # 1. Determine "latest" available date or use today's date if realtime.
    # For caching to work effectively with ETL, we should check what's the max date in DB.
    try:
        ch_client = get_clickhouse_client()
        result_date = ch_client.execute(
            "SELECT max(report_date) FROM bionicpro.user_daily_reports WHERE user_id = %(user_id)s",
            {'user_id': user_id}
        )
        if not result_date or not result_date[0][0]:
            # No data found at all
             return {"message": "No reports found for this user."}

        latest_date = result_date[0][0] # date object
        report_key = f"{user_id}/{latest_date}.json"

        s3 = get_s3_client()

        # 2. Check S3
        try:
            s3.head_object(Bucket=S3_BUCKET, Key=report_key)
            # Found in S3 -> Return CDN URL
            # Note: We append the key to the CDN base URL.
            # Assuming Nginx proxies / to bucket root or /reports/ to bucket/reports
            # Based on nginx.conf: proxy_pass http://minio:9000. Minio paths are /bucket/key
            # So CDN URL should be http://localhost:9090/reports/user_id/date.json
            cdn_link = f"{CDN_URL}/{S3_BUCKET}/{report_key}"
            return {"user_id": user_id, "report_url": cdn_link}
        except Exception:
            # Not found in S3 (ClientError) -> Generate
            pass

        # 3. Generate from ClickHouse
        result = ch_client.execute(
            """
            SELECT report_date, avg_signal, min_battery, total_actions
            FROM bionicpro.user_daily_reports
            WHERE user_id = %(user_id)s
            ORDER BY report_date DESC
            """,
            {'user_id': user_id}
        )

        reports = []
        for row in result:
            reports.append({
                "date": str(row[0]),
                "avg_signal": row[1],
                "min_battery": row[2],
                "total_actions": row[3]
            })

        full_report = {"user_id": user_id, "reports": reports}

        # 4. Upload to S3
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=report_key,
            Body=json.dumps(full_report),
            ContentType='application/json'
        )

        cdn_link = f"{CDN_URL}/{S3_BUCKET}/{report_key}"
        return {"user_id": user_id, "report_url": cdn_link}

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving reports")

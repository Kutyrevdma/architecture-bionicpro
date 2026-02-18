from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from clickhouse_driver import Client
from datetime import datetime, timedelta
import pandas as pd

# Configuration
SOURCE_CONN_ID = "postgres_default"
CLICKHOUSE_HOST = "clickhouse"

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2023, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'bionicpro_etl_daily_telemetry',
    default_args=default_args,
    description='ETL pipeline for BionicPRO telemetry (CRM via CDC)',
    schedule_interval='0 1 * * *',
    catchup=False
)

def extract_telemetry_data(**kwargs):
    pg_hook = PostgresHook(postgres_conn_id=SOURCE_CONN_ID)
    sql = """
        SELECT user_id, date(timestamp) as log_date, avg(signal_strength) as avg_signal,
               min(battery_level) as min_battery, count(action) as total_actions
        FROM telemetry_logs
        GROUP BY user_id, date(timestamp)
    """
    df = pg_hook.get_pandas_df(sql)
    return df.to_dict('records')

def transform_telemetry(**kwargs):
    ti = kwargs['ti']
    telemetry_data = ti.xcom_pull(task_ids='extract_telemetry')

    if not telemetry_data:
        return []

    df = pd.DataFrame(telemetry_data)

    # Just format types if needed, no CRM merge here
    df['log_date'] = pd.to_datetime(df['log_date']).dt.date

    return df.to_dict('records')

def load_to_clickhouse(**kwargs):
    ti = kwargs['ti']
    data = ti.xcom_pull(task_ids='transform_telemetry')

    if not data:
        print("No data to load")
        return

    client = Client(CLICKHOUSE_HOST)

    # Ensure raw table exists (should be created by init script, but safe to check)
    client.execute('CREATE DATABASE IF NOT EXISTS bionicpro')
    client.execute('''
        CREATE TABLE IF NOT EXISTS bionicpro.telemetry_raw (
            user_id String,
            log_date Date,
            avg_signal Float32,
            min_battery Int32,
            total_actions Int32
        ) ENGINE = MergeTree()
        ORDER BY (user_id, log_date)
    ''')

    # Insert raw telemetry
    client.execute('INSERT INTO bionicpro.telemetry_raw VALUES', data)

t1 = PythonOperator(
    task_id='extract_telemetry',
    python_callable=extract_telemetry_data,
    dag=dag,
)

t2 = PythonOperator(
    task_id='transform_telemetry',
    python_callable=transform_telemetry,
    provide_context=True,
    dag=dag,
)

t3 = PythonOperator(
    task_id='load_to_clickhouse',
    python_callable=load_to_clickhouse,
    provide_context=True,
    dag=dag,
)

t1 >> t2 >> t3

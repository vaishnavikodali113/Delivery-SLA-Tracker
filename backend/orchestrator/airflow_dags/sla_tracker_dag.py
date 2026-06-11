from datetime import datetime, timedelta
import os
import sys
from airflow import DAG
from airflow.operators.python import PythonOperator

# Ensure backend directory is in python path so python can find the ETL script
# in the Airflow environment
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from orchestrator.etl import run_etl_pipeline

default_args = {
    'owner': 'data_engineering',
    'depends_on_past': False,
    'start_date': datetime(2026, 6, 11),
    'email': ['alerts@deliverysla.com'],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'delivery_sla_etl_pipeline',
    default_args=default_args,
    description='Orchestrates the extraction of delivery events, runs DQ validation and SLA classification, and loads the analytical DuckDB database.',
    schedule_interval='@hourly',
    catchup=False,
    tags=['delivery', 'sla', 'etl', 'star_schema'],
) as dag:

    def trigger_etl():
        """Wrapper function to invoke the ETL pipeline from Airflow context."""
        result = run_etl_pipeline()
        print(f"ETL completed successfully. Run summary: {result}")
        return result

    run_etl_task = PythonOperator(
        task_id='run_sla_etl_batch',
        python_callable=trigger_etl,
    )

    run_etl_task

from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.decorators import dag, task
from datetime import datetime, timedelta
import json
from kafka import KafkaProducer, errors
import logging
from boxoffice_api import BoxOffice

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=1),
}

API_KEY = "bbfefc51"
box_office = BoxOffice(api_key=API_KEY)

KAFKA_BROKER = 'kafka:9092'
KAFKA_TOPIC = 'box_office_kafka_topic'


def create_kafka_producer():
    try:
        producer = KafkaProducer(bootstrap_servers=[KAFKA_BROKER])
    except errors.NoBrokersAvailable:
        logging.info(
            "We assume that we are running locally, so we use localhost instead of kafka and the external "
            "port 9094"
        )
        producer = KafkaProducer(bootstrap_servers=["localhost:9094"])

    return producer


@task
def fetch_box_office_data(dt):
    bo_daily_data = box_office.get_daily(dt)
    logging.info(f'{dt} loaded')
    logging.info(bo_daily_data)
    return bo_daily_data


@task(retries=3, retry_delay=timedelta(minutes=3))
def send_to_kafka(dt, bo_daily_data):
    producer = create_kafka_producer()
    
    for row in bo_daily_data:
        key = f"{dt}".encode('utf-8')
        value = json.dumps(row).encode("utf-8")
        producer.send(KAFKA_TOPIC, value=value, key=key)

def decide_which_path(data_to_send, dt):
    if data_to_send:
        return f'send_to_kafka_{dt}'
    else:
        return f'skip_send_{dt}'

@task
def skip_send():
    logging.info("No data to send to Kafka")

@dag(default_args=default_args, schedule_interval=None, dag_id='2-boxofficemojo_to_kafka', description='Fetch box office data and send to Kafka sequentially', start_date=datetime.now()- timedelta(days=7))

def boxofficemojo_to_kafka_dag():
    for i in range(7): 
        dt = (datetime.now() - timedelta(days=i+1)).strftime('%Y-%m-%d')
        data_to_send = fetch_box_office_data(dt)
        
        branching = BranchPythonOperator(
            task_id=f'branching_{dt}',
            python_callable=decide_which_path,
            op_args=[data_to_send, dt]
        )

        send_task = send_to_kafka.override(task_id=f'send_to_kafka_{dt}')(dt, data_to_send)
        skip_task = skip_send.override(task_id=f'skip_send_{dt}')()

        data_to_send >> branching
        branching >> send_task
        branching >> skip_task


dag_instance = boxofficemojo_to_kafka_dag()

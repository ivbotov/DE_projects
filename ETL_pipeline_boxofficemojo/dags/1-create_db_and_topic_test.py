from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.utils.dates import days_ago
import logging

from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError

def check_connection():
    hook = PostgresHook(postgres_conn_id='postgres_airflow')
    try:
        with hook.get_conn() as conn:
            with conn.cursor() as cursor:
                cursor.execute('SELECT 1')
                result = cursor.fetchone()
                if result:
                    logging.info("Successfully connected to the database and executed test query.")
                    return True
                else:
                    logging.error("Test query did not return expected result.")
                    raise ValueError("Unable to connect to the database")
    except Exception as e:
        logging.error(f"Failed to connect to the database: {str(e)}")
        raise

def create_database():
    hook = PostgresHook(postgres_conn_id='postgres_airflow')
    try:
        # Подключаемся к базе данных PostgreSQL
        conn = hook.get_conn()
        conn.autocommit = True
        cursor = conn.cursor()

        # Создаем базу данных box_office
        cursor.execute("CREATE DATABASE box_office;")
        logging.info("Successfully created database 'box_office'.")
    except Exception as e:
        logging.error(f"Failed to create database 'box_office': {str(e)}")
    finally:
        cursor.close()
        conn.close()

def create_table():
    hook = PostgresHook(postgres_conn_id='postgres_airflow', schema='box_office')
    try:
        with hook.get_conn() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "CREATE TABLE IF NOT EXISTS public.test_table ("
                    "id SERIAL PRIMARY KEY, "
                    "name VARCHAR(50)"
                    ");"
                )
                conn.commit()
                logging.info("Successfully created table 'test_table' in schema 'public'.")
    except Exception as e:
        logging.error(f"Failed to create table 'test_table' in schema 'public': {str(e)}")
        raise

def create_topic():
    admin_client = KafkaAdminClient(
        bootstrap_servers="kafka:9092", 
        client_id='test'
    )
    topic_name = "box_office"
    try:
        admin_client.create_topics(
            [NewTopic(name=topic_name, num_partitions=1, replication_factor=1)]
        )
        logging.info(f"Topic {topic_name} created!")
    except TopicAlreadyExistsError:
        logging.warning(f"Topic {topic_name} already exists.")
    except Exception as e:
        logging.error(f"Failed to create topic {topic_name}: {str(e)}")
        raise

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
}

with DAG(
    '1-create_db_and_topic_test',
    default_args=default_args,
    description='A simple DAG to create a postgres DB and table and Kafka Topic',
    schedule_interval=None,
    start_date=days_ago(1),
    tags=['example'],
) as dag:
    
    check_conn = PythonOperator(
        task_id='1.1-check_connection',
        python_callable=check_connection,
    )

    create_database_task = PythonOperator(
        task_id='1.2-create_database',
        python_callable=create_database,
    )

    create_table_task = PythonOperator(
        task_id='1.3-create_table',
        python_callable=create_table,
    )

    create_topic_task = PythonOperator(
        task_id='2-create_kafka_topic',
        python_callable=create_topic,
    )

    check_conn >> create_database_task >> create_table_task
    check_conn >> create_topic_task

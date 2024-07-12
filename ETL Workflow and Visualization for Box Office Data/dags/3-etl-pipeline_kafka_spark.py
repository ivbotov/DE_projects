from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, regexp_replace, when, to_date, from_json
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, IntegerType
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

KAFKA_BROKER = 'kafka:9092'
KAFKA_TOPIC = 'box_office_kafka_topic'
POSTGRES_URL = 'jdbc:postgresql://postgres:5432/box_office'
POSTGRES_PROPERTIES = {
    'user': 'airflow',
    'password': 'airflow',
    'driver': 'org.postgresql.Driver'
}

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime.now(),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    '3-etl-pipeline_kafka_spark',
    default_args=default_args,
    description='Stream data from Kafka, process with Spark, and store in DataFrame',
    schedule_interval=timedelta(days=1),
)

def process_kafka_stream():
    spark = SparkSession.builder \
        .appName("KafkaSparkStreaming") \
        .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.1.2,org.postgresql:postgresql:42.2.23") \
        .getOrCreate()

    df = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BROKER) \
        .option("subscribe", KAFKA_TOPIC) \
        .option("startingOffsets", "earliest") \
        .option("group.id", "my_consumer_group") \
        .load()

    df = df.selectExpr("CAST(key AS STRING)", "CAST(value AS STRING)")



    def process_row(row):
        selected_columns = [
            "%± LW", "%± YD", "Avg", "BoxOffice", "Daily", "Days", "Release",
            "Theaters", "To Date", "imdbRating", "imdbVotes", "date"]
        
        message = json.loads(row.value)
        flattened_message = {col: message.get(col, None) for col in          
                             selected_columns}
        flattened_message['date'] = row.key

        return flattened_message

    def foreach_batch_function(batch_df, epoch_id):
        schema = StructType([
            StructField("date", StringType(), True),
            StructField("Release", StringType(), True),
            StructField("Daily", StringType(), True),
            StructField("%± LW", StringType(), True),
            StructField("%± YD", StringType(), True),
            StructField("Avg", StringType(), True),
            StructField("Days", StringType(), True),
            StructField("Theaters", StringType(), True),
            StructField("To Date", StringType(), True),
            StructField("imdbRating", StringType(), True),
            StructField("imdbVotes", StringType(), True)
        ])
        
        transformed_df = batch_df.rdd.map(lambda row: process_row(row)).toDF(schema=schema)
        
        def clean_value(column):
            return when(col(column) == '-', None) \
                .otherwise(regexp_replace(regexp_replace(col(column), '[\%+±,\$ ]', ''), '', '').cast('float'))

        transformed_df = transformed_df \
            .withColumn("Daily", regexp_replace(col("Daily"), '[\$,]', '').cast('int')) \
            .withColumn("%± YD", clean_value("%± YD")) \
            .withColumn("%± LW", clean_value("%± LW")) \
            .withColumn("Avg", clean_value("Avg")) \
            .withColumn("To Date", regexp_replace(col("To Date"), '[\$,]', '').cast('int')) \
            .withColumn("date", to_date(col("date"), 'yyyy-MM-dd')) \
            .withColumn("Theaters", clean_value("Theaters").cast('int')) \
            .withColumn("Days", clean_value("Days").cast('int')) \
            .withColumn("imdbVotes", clean_value("imdbVotes").cast('int')) \
            .withColumn("imdbRating", clean_value("imdbRating").cast('float'))
        
        logging.info(f"Processed DataFrame Schema: \n")
        transformed_df.printSchema()
        logging.info(f"Sample DataFrame: \n")
        transformed_df.show(10, truncate=False)
        
        # Write Spark DataFrame to PostgreSQL
        transformed_df.write.jdbc(url=POSTGRES_URL, table='box_office', mode='overwrite', properties=POSTGRES_PROPERTIES)

    query = df.writeStream \
        .foreachBatch(foreach_batch_function) \
        .start()
    
    query.awaitTermination(timeout=15)
    query.stop() 
    spark.stop()

process_kafka_stream_task = PythonOperator(
    task_id='process_kafka_stream_task',
    python_callable=process_kafka_stream,
    dag=dag,
)

process_kafka_stream_task

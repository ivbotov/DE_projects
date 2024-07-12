FROM apache/airflow:latest-python3.8
USER root
RUN apt-get update && apt-get install -y openjdk-17-jdk

ARG AIRFLOW_HOME=/opt/airflow

# Копирование необходимых файлов в контейнер
COPY requirements.txt $AIRFLOW_HOME/requirements.txt
COPY dags /opt/airflow/dags
COPY airflow-scripts /opt/airflow/airflow-scripts
# Установка прав на выполнение для скрипта
RUN chmod +x /opt/airflow/airflow-scripts/airflow-entrypoint.sh

# Проверка наличия файлов
RUN ls -la $AIRFLOW_HOME && cat $AIRFLOW_HOME/requirements.txt

USER airflow

# Удаление кеша pip, обновление pip и установка зависимостей из requirements.txt
RUN pip cache purge && \
    pip install --upgrade pip && \
    pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r $AIRFLOW_HOME/requirements.txt

USER ${AIRFLOW_UID}

# Указание точки входа
ENTRYPOINT [ "/opt/airflow/airflow-scripts/airflow-entrypoint.sh" ]


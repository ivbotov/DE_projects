#!/usr/bin/env bash

set -e  # остановить скрипт при ошибке

# Инициализация базы данных
airflow db reset -y  # используем db reset вместо resetdb
airflow db init

# Переменная окружения для отключения аутентификации
export AIRFLOW__WEBSERVER__AUTH_BACKEND=airflow.api.auth.backend.default

# Создание пользователя
airflow users create -r Admin -u admin -e admin@admin.com -f admin -l admin -p admin

# Добавление подключения
airflow connections add 'postgres_airflow' \
    --conn-type 'postgres' \
    --conn-login 'airflow' \
    --conn-password 'airflow' \
    --conn-host 'postgres' \
    --conn-port '5432'

# Запуск scheduler и webserver
airflow scheduler &  # запускаем в фоне
airflow webserver    # запускаем в основном потоке

# Даем 10 секунд на инициализацию веб-сервера и других сервисов
sleep 10

# Триггерим DAG '1-create_db_and_topic_test'
airflow dags trigger 1-create_db_and_topic_test

# Блокируем контейнер, чтобы он не завершился
tail -f /dev/null
#!/bin/bash
set -e

# Проверка, существует ли топик, и создание его, если не существует
TOPIC_NAME="test_topic"
BROKER="kafka:9092"

# Проверка существования топика
TOPIC_EXISTS=$(kafka-topics.sh --bootstrap-server $BROKER --list | grep $TOPIC_NAME || true)

if [ -z "$TOPIC_EXISTS" ]; then
  echo "Топик $TOPIC_NAME не существует. Создаю его..."
  kafka-topics.sh --bootstrap-server $BROKER --create --topic $TOPIC_NAME --partitions 1 --replication-factor 1
else
  echo "Топик $TOPIC_NAME уже существует."
fi

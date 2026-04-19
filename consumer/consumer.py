from kafka import KafkaConsumer
import json

# Create Kafka Consumer
consumer = KafkaConsumer(
    'booking-events',
    bootstrap_servers='localhost:9092',
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
)

print("Consumer started...")

for message in consumer:
    print("Consumed:", message.value)
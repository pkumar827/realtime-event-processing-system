from kafka import KafkaProducer
import json
import time
import random

# Create Kafka Producer
producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# Event types (simulating booking system)
events = ["search", "view", "select_seat", "payment", "booking"]

print("Producer started...")

while True:
    data = {
        "user_id": random.randint(1, 100000),
        "event": random.choice(events),
        "tickets": random.randint(1, 5),
        "timestamp": time.time()
    }

    # Send data to Kafka topic
    producer.send("booking-events", data)

    print("Produced:", data)

    time.sleep(0.2)
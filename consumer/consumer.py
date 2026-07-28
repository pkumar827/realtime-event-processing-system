"""
Booking event worker (consumer).

Runs as a member of a Kafka consumer group, so multiple workers automatically
share the topic's partitions and process events in parallel. This is the unit
the auto-scaler starts and stops.

Each worker:
  - joins the consumer group (so partitions are load-balanced across workers)
  - simulates a fixed amount of processing work per event (config: WORK_MS)
  - measures processing latency (now - event timestamp), reported per interval
  - prints periodic stats so you can see it coping or falling behind

Run one worker:
    python consumer/consumer.py --worker-id w1

Run more (in separate terminals) to share the load:
    python consumer/consumer.py --worker-id w2
    python consumer/consumer.py --worker-id w3
"""

import argparse
import json
import os
import signal
import sys
import time

from kafka import KafkaConsumer

# Make "config" importable regardless of launch directory.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings


running = True


def _handle_sigint(signum, frame):
    global running
    running = False


def process_event(event):
    """
    Simulate real per-event work (validation, a DB write, a fraud check, etc.)
    as a fixed delay. This is the knob that decides how much a single worker can
    handle: WORK_MS = 5 -> ~200 events/sec per worker.
    """
    time.sleep(settings.WORK_MS / 1000.0)


def run(args):
    consumer = KafkaConsumer(
        args.topic,
        bootstrap_servers=args.bootstrap,
        group_id=settings.CONSUMER_GROUP,
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        key_deserializer=lambda k: k.decode("utf-8") if k else None,
        auto_offset_reset="latest",   # only process new events, not old backlog
        enable_auto_commit=True,
        # Poll in reasonably small batches so one slow worker doesn't hoard a
        # huge chunk of events before the group can rebalance.
        max_poll_records=100,
    )

    worker = args.worker_id
    processed = 0
    since_report = 0
    latency_sum = 0.0       # reset each report window
    latency_count = 0       # events counted in this window
    latency_max = 0.0
    start = time.perf_counter()
    last_report = start

    print(f"[{worker}] started | group={settings.CONSUMER_GROUP} | "
          f"work={settings.WORK_MS}ms/event")
    print(f"[{worker}] processed  rate/s  avg_latency_ms  max_latency_ms")

    while running:
        # Poll with a timeout so the loop stays responsive to Ctrl+C even when
        # no messages are arriving.
        records = consumer.poll(timeout_ms=500)

        for _tp, messages in records.items():
            for message in messages:
                event = message.value

                # Latency = how long the event waited from creation to now.
                # Event timestamp is epoch millis; guard against missing field.
                event_ts = event.get("timestamp")
                if event_ts is not None:
                    latency_ms = (time.time() * 1000) - event_ts
                    if latency_ms < 0:
                        latency_ms = 0.0
                    latency_sum += latency_ms
                    latency_count += 1
                    latency_max = max(latency_max, latency_ms)

                process_event(event)
                processed += 1
                since_report += 1

            if not running:
                break

        # Report about once per second.
        now = time.perf_counter()
        elapsed = now - last_report
        if elapsed >= 1.0:
            rate = since_report / elapsed
            avg_latency = (latency_sum / latency_count) if latency_count else 0.0
            print(f"[{worker}] {processed:9}  {rate:6.0f}  "
                  f"{avg_latency:14.0f}  {latency_max:14.0f}")
            last_report = now
            since_report = 0
            latency_sum = 0.0      # reset window: avg reflects THIS interval only
            latency_count = 0
            latency_max = 0.0

    consumer.close()
    total_elapsed = time.perf_counter() - start
    avg_rate = processed / total_elapsed if total_elapsed > 0 else 0
    print(f"\n[{worker}] stopped. Processed {processed} events in "
          f"{total_elapsed:.1f}s (avg {avg_rate:.0f}/s).")


def parse_args():
    p = argparse.ArgumentParser(description="Booking event worker (consumer)")
    p.add_argument("--worker-id", default="w1",
                   help="identifier for this worker in logs/metrics")
    p.add_argument("--bootstrap", default=settings.KAFKA_BOOTSTRAP_SERVERS)
    p.add_argument("--topic", default=settings.TOPIC_NAME)
    return p.parse_args()


def main():
    signal.signal(signal.SIGINT, _handle_sigint)
    args = parse_args()
    run(args)


if __name__ == "__main__":
    main()
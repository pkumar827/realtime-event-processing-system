"""
Auto-scaler (the supervisor).

This is the core of the project. It runs a control loop:

    measure lag  ->  decide  ->  spawn / kill a worker  ->  cool down

Lag = events produced but not yet processed by the consumer group. It is read
directly from Kafka through a single PERSISTENT admin/consumer connection that
is opened once and reused every poll -- so there is no per-poll JVM startup or
reconnect overhead (important on a low-RAM machine).

Workers are just instances of consumer/consumer.py launched as subprocesses, so
the scaler reuses the exact worker that was already built and tested.

Decision rules (all configurable in config/settings.py):
    lag > SCALE_UP_LAG    and workers < MAX_WORKERS  -> add a worker
    lag < SCALE_DOWN_LAG  and workers > MIN_WORKERS  -> remove a worker
    a cooldown after every action prevents rapid flapping.

The scaler also logs metrics (lag, workers, throughput) to a CSV each poll,
for later plotting. Use --no-scale for a fixed-1-worker baseline run.

Run:
    python scaler/auto_scaler.py                          # auto-scaling
    python scaler/auto_scaler.py --no-scale               # baseline (no scaling)
    python scaler/auto_scaler.py --metrics-file out.csv   # choose CSV path
"""

import os
import signal
import subprocess
import sys
import time

from kafka import KafkaConsumer
from kafka.admin import KafkaAdminClient
from kafka.structs import TopicPartition

# Make "config" importable and locate the repo root (to launch workers).
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(REPO_ROOT)
from config import settings


running = True


def _handle_sigint(signum, frame):
    global running
    running = False


# --------------------------------------------------------------------------
# Lag reader -- one persistent connection, reused every poll
# --------------------------------------------------------------------------

class LagReader:
    """
    Reads total consumer-group lag from Kafka using persistent connections.

    lag(partition) = log_end_offset(partition) - committed_offset(partition)
    total lag       = sum over all partitions of the topic
    """

    def __init__(self, bootstrap, group, topic):
        self.group = group
        self.topic = topic
        # Persistent admin client: reads the group's committed offsets.
        self.admin = KafkaAdminClient(bootstrap_servers=bootstrap)
        # Persistent consumer: used only to read log-end (high-watermark)
        # offsets. It does NOT join the working group, so it never steals
        # partitions from real workers.
        self.reader = KafkaConsumer(
            bootstrap_servers=bootstrap,
            group_id=None,
            enable_auto_commit=False,
        )
        # Resolve the topic's partitions once.
        parts = self.reader.partitions_for_topic(topic) or set()
        self.partitions = [TopicPartition(topic, p) for p in parts]

    def snapshot(self):
        """
        Return (total_lag, committed_total) or (None, None) if not determinable.
        committed_total = total events processed by the group so far (sum of
        committed offsets) -- used to derive throughput between polls.
        """
        if not self.partitions:
            parts = self.reader.partitions_for_topic(self.topic) or set()
            self.partitions = [TopicPartition(self.topic, p) for p in parts]
            if not self.partitions:
                return None, None

        try:
            committed = self.admin.list_consumer_group_offsets(self.group)
        except Exception:
            return None, None

        if not committed:
            return None, None

        end_offsets = self.reader.end_offsets(self.partitions)

        total_lag = 0
        committed_total = 0
        for tp in self.partitions:
            end = end_offsets.get(tp, 0)
            meta = committed.get(tp)
            current = meta.offset if meta is not None else 0
            total_lag += max(end - current, 0)
            committed_total += current
        return total_lag, committed_total

    def total_lag(self):
        """Backwards-compatible: return just the lag."""
        lag, _ = self.snapshot()
        return lag

    def close(self):
        try:
            self.reader.close()
        except Exception:
            pass
        try:
            self.admin.close()
        except Exception:
            pass


# --------------------------------------------------------------------------
# Worker management
# --------------------------------------------------------------------------

class WorkerManager:
    """Starts and stops consumer.py subprocesses; tracks how many are running."""

    def __init__(self):
        self.workers = []      # list of (worker_id, Popen)
        self.counter = 0
        self.consumer_path = os.path.join(REPO_ROOT, "consumer", "consumer.py")

    def count(self):
        return len(self.workers)

    def add(self):
        self.counter += 1
        wid = f"w{self.counter}"
        # start_new_session=True puts the worker in its own process group so a
        # Ctrl+C in the scaler's terminal doesn't kill it directly -- the scaler
        # stays in control of stopping workers.
        proc = subprocess.Popen(
            [sys.executable, self.consumer_path, "--worker-id", wid],
            cwd=REPO_ROOT,
            start_new_session=True,
        )
        self.workers.append((wid, proc))
        return wid

    def remove(self):
        """Stop the most recently started worker (graceful SIGINT)."""
        if not self.workers:
            return None
        wid, proc = self.workers.pop()
        proc.send_signal(signal.SIGINT)   # let it leave the group cleanly
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        return wid

    def stop_all(self):
        for _wid, proc in self.workers:
            proc.send_signal(signal.SIGINT)
        for _wid, proc in self.workers:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        self.workers = []


# --------------------------------------------------------------------------
# Control loop
# --------------------------------------------------------------------------

def decide(lag, worker_count):
    """
    Pure decision function (no side effects) so it is easy to test.
    Returns "up", "down", or "hold".
    """
    if lag is None:
        return "hold"
    if lag > settings.SCALE_UP_LAG and worker_count < settings.MAX_WORKERS:
        return "up"
    if lag < settings.SCALE_DOWN_LAG and worker_count > settings.MIN_WORKERS:
        return "down"
    return "hold"


def main():
    signal.signal(signal.SIGINT, _handle_sigint)

    import argparse
    p = argparse.ArgumentParser(description="Lag-based auto-scaler")
    p.add_argument("--no-scale", action="store_true",
                   help="hold at MIN_WORKERS and never scale (baseline run)")
    p.add_argument("--metrics-file", default=None,
                   help="path to write a metrics CSV (default: metrics/run_<ts>.csv)")
    args = p.parse_args()

    # Decide where to log metrics.
    metrics_dir = os.path.join(REPO_ROOT, "metrics")
    os.makedirs(metrics_dir, exist_ok=True)
    if args.metrics_file:
        metrics_path = args.metrics_file
    else:
        tag = "baseline" if args.no_scale else "scaler"
        ts = time.strftime("%Y%m%d_%H%M%S")
        metrics_path = os.path.join(metrics_dir, f"run_{ts}_{tag}.csv")

    lag_reader = LagReader(
        settings.KAFKA_BOOTSTRAP_SERVERS,
        settings.CONSUMER_GROUP,
        settings.TOPIC_NAME,
    )
    workers = WorkerManager()

    mode_label = "BASELINE (no scaling)" if args.no_scale else "AUTO-SCALING"
    print(f"Auto-scaler started -- mode: {mode_label}")
    print(f"  up>{settings.SCALE_UP_LAG}  down<{settings.SCALE_DOWN_LAG}  "
          f"cooldown={settings.SCALE_COOLDOWN_SEC}s  "
          f"min={settings.MIN_WORKERS} max={settings.MAX_WORKERS}")
    print(f"  logging metrics to: {metrics_path}")

    # Start at the minimum worker count.
    for _ in range(settings.MIN_WORKERS):
        wid = workers.add()
        print(f"  start -> {wid} (workers={workers.count()})")

    # Open the metrics CSV and write the header.
    metrics_file = open(metrics_path, "w", buffering=1)  # line-buffered
    metrics_file.write("elapsed_sec,lag,workers,throughput\n")

    last_action = 0.0
    loop_start = time.time()
    prev_committed = None
    prev_time = None

    print("\n  time     lag  workers  thrpt  action")

    while running:
        lag, committed_total = lag_reader.snapshot()
        now = time.time()

        # Throughput = events processed since last poll / elapsed.
        throughput = 0.0
        if committed_total is not None and prev_committed is not None and prev_time:
            dt = now - prev_time
            if dt > 0:
                throughput = max(committed_total - prev_committed, 0) / dt
        if committed_total is not None:
            prev_committed = committed_total
            prev_time = now

        in_cooldown = (now - last_action) < settings.SCALE_COOLDOWN_SEC

        # In baseline mode, never scale; otherwise use the decision rule.
        action = "hold" if args.no_scale else decide(lag, workers.count())
        applied = "hold"

        if action != "hold" and not in_cooldown:
            if action == "up":
                wid = workers.add()
                applied = f"UP  -> {wid}"
            else:
                wid = workers.remove()
                applied = f"DOWN-> {wid}"
            last_action = now
        elif action != "hold" and in_cooldown:
            applied = f"{action} (cooldown)"

        elapsed = now - loop_start
        # Write a metrics row (skip rows where lag is unknown).
        if lag is not None:
            metrics_file.write(f"{elapsed:.1f},{lag},{workers.count()},{throughput:.1f}\n")

        lag_str = "  -  " if lag is None else f"{lag:5d}"
        print(f"  {time.strftime('%H:%M:%S')}  {lag_str}  {workers.count():^7}  "
              f"{throughput:5.0f}  {applied}")

        # Sleep in short slices so Ctrl+C is responsive.
        slept = 0.0
        while slept < settings.SCALER_POLL_SEC and running:
            time.sleep(0.2)
            slept += 0.2

    print("\nShutting down scaler -> stopping all workers...")
    workers.stop_all()
    lag_reader.close()
    metrics_file.close()
    print(f"Scaler stopped. Metrics saved to {metrics_path}")


if __name__ == "__main__":
    main()
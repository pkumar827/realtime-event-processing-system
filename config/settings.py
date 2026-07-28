"""
Central configuration for the Real-Time Event Processing System.

All tunable numbers live here so we can adjust behaviour without editing
logic. Values are deliberately conservative for a 4 GB RAM machine and can
be overridden per-run via command-line flags on the producer.
"""

# --- Kafka connection ---
KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
TOPIC_NAME = "booking-events"

# --- Load generation defaults ---
# Baseline = quiet browsing traffic. Peak = the launch surge.
# These are TARGET rates (messages/second). Actual achieved rate is measured
# and logged; on a low-spec machine the actual peak may be lower, which is fine
# because the benchmark reports measured numbers, not the target.
BASE_RATE = 40          # msg/sec, quiet period
PEAK_RATE = 500        # msg/sec, surge peak (~40x baseline)

# Step profile (mode=steps): predictable stages for a live demo.
# Each stage is (duration_seconds, rate). The scaler should visibly react
# when the rate jumps to peak and hold there.
STEP_PROFILE = [
    (30, BASE_RATE),    # warm-up: quiet baseline
    (60, PEAK_RATE),    # spike: jump straight to peak and HOLD (demo-friendly)
    (30, BASE_RATE),    # cool-down: back to baseline
]

# Curve profile (mode=curve): a smooth, realistic surge for report graphs.
# Modeled as a Gaussian burst centred partway through the run.
CURVE_DURATION = 120    # total seconds for one curve run
CURVE_PEAK_CENTER = 0.55  # peak occurs at 55% of the run
CURVE_WIDTH = 0.15      # spread of the surge (fraction of duration)

# --- Session simulation ---
# Number of concurrent booking sessions kept "active" at once. Bounded to keep
# memory small. Each session progresses through the booking funnel and shares
# consistent context (city, movie, device) across its events.
SESSION_POOL_TARGET = 100

# --- Internal ---
TICK_SECONDS = 0.1      # rate is recomputed and applied every 100 ms

# --- Worker (consumer) settings ---
# Consumer group: all workers share this group so Kafka load-balances the
# topic's partitions across them. Partition count (3) is the worker ceiling.
CONSUMER_GROUP = "booking-workers"

# Simulated processing work per event, in milliseconds. This sets one worker's
# capacity: WORK_MS=5 -> ~200 events/sec. Tuning lever for the scaling demo.
WORK_MS = 5
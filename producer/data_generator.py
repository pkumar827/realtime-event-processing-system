"""
Booking event generator (producer).

Simulates a BookMyShow-style stream of booking events and publishes them to
Kafka. Three load modes:

  --mode steps   Fixed stages (baseline -> peak hold -> baseline). Predictable
                 and repeatable; good for a quick live demo.

  --mode curve   Smooth Gaussian surge (quiet -> ramp -> peak -> tail-off).
                 Realistic shape; use this to capture graphs for the report.

  --mode cycles  Repeating surges: peak for a while, drop to baseline, repeat.
                 Makes the scaler cycle up and down several times in one run.

Events are keyed by session_id, so every event from one booking session lands
on the same partition and stays ordered.

Examples:
    python producer/data_generator.py --mode steps
    python producer/data_generator.py --mode curve --duration 120
    python producer/data_generator.py --mode cycles
"""

import argparse
import json
import math
import os
import random
import signal
import sys
import time
import uuid

from kafka import KafkaProducer

# Make "config" importable no matter which directory we launch from:
# add the repo root (the parent of this file's folder) to the path.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings


# --------------------------------------------------------------------------
# Booking session model
# --------------------------------------------------------------------------
# A session moves through the booking funnel. Each step may "abandon" (the user
# leaves), which is realistic drop-off. Context (city, movie, device) is fixed
# for the life of the session so its events look coherent.

CITIES = ["Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Chennai",
          "Kolkata", "Pune", "Jaipur", "Ahmedabad", "Lucknow"]
SEAT_CATEGORIES = ["regular", "premium", "recliner"]
PLATFORMS = ["android", "ios", "web"]
PAYMENT_METHODS = ["upi", "card", "netbanking"]

# Funnel stages in order. Value = probability of continuing to the next stage
# (otherwise the session abandons at the current stage).
FUNNEL = [
    ("search", 0.75),
    ("view", 0.55),
    ("select_seat", 0.60),
    ("add_to_cart", 0.70),
    ("payment_initiated", 0.90),
    # terminal stage handled specially below
]
SEAT_PRICES = {"regular": 180, "premium": 320, "recliner": 550}


def new_session():
    """Create a fresh booking session with fixed context and stage 0."""
    seat_category = random.choice(SEAT_CATEGORIES)
    seat_count = random.randint(1, 6)
    return {
        "session_id": "sess-" + uuid.uuid4().hex[:12],
        "user_id": random.randint(1, 500_000),
        "city": random.choice(CITIES),
        "movie_id": "MOV" + str(random.randint(1000, 1999)),
        "theatre_id": "TH" + str(random.randint(100, 999)),
        "show_time": random.choice(["10:00", "13:15", "16:30", "19:45", "22:30"]),
        "platform": random.choice(PLATFORMS),
        "app_version": random.choice(["5.2.1", "5.3.0", "5.3.1", "6.0.0"]),
        "seat_category": seat_category,
        "seat_count": seat_count,
        "amount": seat_count * SEAT_PRICES[seat_category],
        "stage": 0,
    }


def build_event(session):
    """Build one event dict for the session's current stage."""
    stage_index = session["stage"]

    if stage_index < len(FUNNEL):
        event_type = FUNNEL[stage_index][0]
    else:
        # Past the last funnel stage -> resolve the payment outcome.
        event_type = "booking_confirmed" if random.random() < 0.85 else "booking_failed"

    # Common envelope
    event = {
        "event_id": uuid.uuid4().hex,
        "event_type": event_type,
        "user_id": session["user_id"],
        "session_id": session["session_id"],
        "timestamp": int(time.time() * 1000),  # epoch millis, for latency calc
        "device": {
            "platform": session["platform"],
            "app_version": session["app_version"],
        },
        "event_details": {
            "city": session["city"],
            "movie_id": session["movie_id"],
        },
    }

    details = event["event_details"]

    if event_type in ("select_seat", "add_to_cart", "payment_initiated",
                      "booking_confirmed", "booking_failed"):
        details["theatre_id"] = session["theatre_id"]
        details["show_time"] = session["show_time"]
        details["seat_category"] = session["seat_category"]
        details["seat_count"] = session["seat_count"]
        details["amount"] = session["amount"]

    if event_type in ("payment_initiated", "booking_confirmed", "booking_failed"):
        event["payment"] = {
            "method": random.choice(PAYMENT_METHODS),
            "amount": session["amount"],
            "status": "success" if event_type == "booking_confirmed"
                      else "failed" if event_type == "booking_failed"
                      else "pending",
        }

    return event


def advance_session(session):
    """
    Move the session forward. Returns True if it stays active, False if it has
    ended (booked, failed, or abandoned) and should be removed from the pool.
    """
    stage_index = session["stage"]

    # Terminal stage already emitted -> session is done.
    if stage_index >= len(FUNNEL):
        return False

    # Decide whether the user continues past this stage or abandons.
    _, continue_prob = FUNNEL[stage_index]
    if random.random() > continue_prob:
        return False  # abandoned here

    session["stage"] += 1
    return True


class SessionPool:
    """Keeps a bounded set of active sessions and hands out the next event."""

    def __init__(self, target_size):
        self.target_size = target_size
        self.sessions = {}

    def _top_up(self):
        while len(self.sessions) < self.target_size:
            s = new_session()
            self.sessions[s["session_id"]] = s

    def next_event(self):
        """Pick an active session, build its current event, advance it."""
        self._top_up()
        sid = random.choice(list(self.sessions.keys()))
        session = self.sessions[sid]
        event = build_event(session)
        still_active = advance_session(session)
        if not still_active:
            del self.sessions[sid]
        return event, session["session_id"]


# --------------------------------------------------------------------------
# Load profiles: how many messages/second at a given elapsed time
# --------------------------------------------------------------------------

class StepProfile:
    """Piecewise-constant rate: fixed stages held for fixed durations."""

    def __init__(self, stages):
        self.stages = stages
        self.total = sum(d for d, _ in stages)

    def rate_at(self, elapsed):
        t = 0.0
        for duration, rate in self.stages:
            t += duration
            if elapsed < t:
                return rate
        return 0.0  # past the end -> stop

    def duration(self):
        return self.total


class CurveProfile:
    """Smooth Gaussian surge: base + (peak-base) * exp(-((t-tc)^2)/(2*w^2))."""

    def __init__(self, base, peak, duration, center_frac, width_frac):
        self.base = base
        self.peak = peak
        self.total = duration
        self.center = duration * center_frac
        self.width = max(duration * width_frac, 1e-6)

    def rate_at(self, elapsed):
        if elapsed >= self.total:
            return 0.0
        bump = math.exp(-((elapsed - self.center) ** 2) / (2 * self.width ** 2))
        return self.base + (self.peak - self.base) * bump

    def duration(self):
        return self.total


class CyclesProfile:
    """Repeating surges: peak for peak_secs, baseline for cool_secs, xN."""

    def __init__(self, base, peak, peak_secs, cool_secs, cycles):
        self.base = base
        self.peak = peak
        self.peak_secs = peak_secs
        self.cool_secs = cool_secs
        self.period = peak_secs + cool_secs
        self.total = self.period * cycles

    def rate_at(self, elapsed):
        if elapsed >= self.total:
            return 0.0
        pos = elapsed % self.period
        return self.peak if pos < self.peak_secs else self.base

    def duration(self):
        return self.total


# --------------------------------------------------------------------------
# Main send loop
# --------------------------------------------------------------------------

running = True


def _handle_sigint(signum, frame):
    global running
    running = False


def run(profile, args):
    producer = KafkaProducer(
        bootstrap_servers=args.bootstrap,
        key_serializer=lambda k: k.encode("utf-8"),
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        acks=1,
        linger_ms=5,          # small batching window -> better throughput
    )
    pool = SessionPool(settings.SESSION_POOL_TARGET)

    total_sent = 0
    carry = 0.0               # fractional messages carried between ticks
    start = time.perf_counter()
    last_report = start
    sent_since_report = 0

    print(f"Producer started | mode={args.mode} | topic={args.topic} | "
          f"duration={profile.duration():.0f}s")
    print("elapsed(s)  target/s  actual/s  total")

    while running:
        elapsed = time.perf_counter() - start
        if elapsed >= profile.duration():
            break

        target_rate = profile.rate_at(elapsed)

        # How many messages to send this tick (accumulate the fractional part).
        carry += target_rate * settings.TICK_SECONDS
        n = int(carry)
        carry -= n

        for _ in range(n):
            event, key = pool.next_event()
            producer.send(args.topic, key=key, value=event)
        total_sent += n
        sent_since_report += n

        # Print a status line about once per second.
        now = time.perf_counter()
        if now - last_report >= 1.0:
            actual = sent_since_report / (now - last_report)
            print(f"{elapsed:9.1f}  {target_rate:8.0f}  {actual:8.0f}  {total_sent}")
            last_report = now
            sent_since_report = 0

        # Sleep the remainder of the tick.
        sleep_for = settings.TICK_SECONDS - (time.perf_counter() - now)
        if sleep_for > 0:
            time.sleep(sleep_for)

    # Graceful shutdown: flush anything buffered, then close.
    print("\nFlushing remaining messages...")
    producer.flush()
    producer.close()
    elapsed = time.perf_counter() - start
    avg = total_sent / elapsed if elapsed > 0 else 0
    print(f"Done. Sent {total_sent} events in {elapsed:.1f}s "
          f"(avg {avg:.0f} msg/s).")


def parse_args():
    p = argparse.ArgumentParser(description="Booking event generator")
    p.add_argument("--mode", choices=["steps", "curve", "cycles"], default="steps",
                   help="load profile: steps (demo), curve (report), cycles (repeating)")
    p.add_argument("--duration", type=int, default=settings.CURVE_DURATION,
                   help="run length in seconds (curve mode)")
    p.add_argument("--base-rate", type=int, default=settings.BASE_RATE)
    p.add_argument("--peak-rate", type=int, default=settings.PEAK_RATE)
    p.add_argument("--bootstrap", default=settings.KAFKA_BOOTSTRAP_SERVERS)
    p.add_argument("--topic", default=settings.TOPIC_NAME)
    return p.parse_args()


def main():
    args = parse_args()
    signal.signal(signal.SIGINT, _handle_sigint)

    if args.mode == "steps":
        # Rebuild the step profile using any overridden rates.
        stages = [(30, args.base_rate), (60, args.peak_rate), (30, args.base_rate)]
        profile = StepProfile(stages)
    elif args.mode == "cycles":
        profile = CyclesProfile(args.base_rate, args.peak_rate,
                                settings.CYCLE_PEAK_SEC, settings.CYCLE_COOL_SEC,
                                settings.CYCLE_COUNT)
    else:
        profile = CurveProfile(args.base_rate, args.peak_rate, args.duration,
                               settings.CURVE_PEAK_CENTER, settings.CURVE_WIDTH)

    run(profile, args)


if __name__ == "__main__":
    main()
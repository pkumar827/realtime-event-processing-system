# Real-Time Scalable Event Processing System with Auto-Scaling Simulation

M.Tech Major Project — Piyush Kumar (M25DE1046)
School of Artificial Intelligence & Data Science, IIT Jodhpur

## What this project does

Ticket-booking platforms (BookMyShow and similar) get hit with sudden traffic
spikes when a popular event opens — the load can jump 10x–100x within seconds.
This project simulates that burst of booking events, streams them through Kafka,
processes them with a pool of consumer workers, and runs an auto-scaler that adds
or removes workers based on how far the consumers are falling behind. The goal is
to show the system keeping latency under control as load rises, with measured
numbers to back it up.

Pipeline:

    Event Generator  →  Kafka (booking-events topic)  →  Consumer workers  →  Auto-Scaler
       (producer)         3 partitions                    (consumer group)     (scales workers)

## Environment and hardware constraints (changes from the proposal)

The original proposal specified Docker (Confluent Kafka + Zookeeper images),
plus Prometheus and Grafana for monitoring. When I set the project up on my
actual development machine, that stack was not workable, so I made some
deliberate changes. Documenting them here because they are engineering
decisions, not shortcuts — the system design and deliverables are unchanged.

**The machine:** Lenovo IdeaPad 330, Intel Core i3-8130U (2 cores / 4 threads),
4 GB RAM, no dedicated GPU, Windows 11. In practice Windows alone uses around
2.5 GB, so free memory sat at a few hundred MB before I started anything.

**The problem:** The Confluent Docker stack runs two JVMs (Kafka and Zookeeper),
which together want roughly 1.5 GB, and Docker Desktop's WSL2 VM adds another
1.5–2 GB on top. That is 5–6 GB of demand on a 4 GB machine. It swapped
constantly and locked up — and the one thing this project is built to do is
generate high load, which is exactly what pushed it over the edge.

What I changed, and why:

- **Dropped Docker, installed everything natively inside WSL2 (Ubuntu).**
  Removed the Docker Desktop VM overhead entirely. Docker was only ever a
  convenience for starting the broker; it is not part of the system's logic.
  Containerization is kept as the documented cloud-deployment path (see Future
  Scope), which is where it actually earns its keep.

- **Dropped Zookeeper — running Kafka in KRaft mode.** Kafka 4.x manages its own
  metadata quorum and no longer needs Zookeeper, so a single node acts as both
  broker and controller. That deletes an entire JVM from the memory budget.

- **Capped the Kafka broker heap at 512 MB** (`-Xmx512m -Xms512m`). Default is
  1 GB; the broker runs comfortably at 512 MB for this workload and leaves room
  for the Python processes.

- **Replaced Prometheus + Grafana with CSV logging + pandas/matplotlib.** A full
  monitoring stack cannot coexist with the broker on 4 GB. Instead the workers
  and scaler log metrics (latency, throughput, consumer lag, worker count) to CSV,
  and I generate the graphs from that with matplotlib. Same evidence, a fraction
  of the memory, and the plots go straight into the report.

- **Kept Apache Kafka.** Kafka is the core streaming technology in the proposal
  and stays exactly that. KRaft is still Apache Kafka — same broker, same client
  API, just without the separate Zookeeper process.

Net effect: the WSL2 memory cap is set to 2 GB, Kafka lives in 512 MB of that,
and Windows keeps the rest. The system runs, and the load simulation runs, on a
4 GB laptop.

## Tech stack

- Python 3
- Apache Kafka 4.3.1 (KRaft mode, no Zookeeper)
- kafka-python-ng (Kafka client)
- psutil (resource monitoring for the scaler)
- pandas + matplotlib (metrics and plots)
- Java 17 (runtime for Kafka)
- WSL2 / Ubuntu (runtime environment)

## Current status

Working:
- Native Kafka (KRaft) running under WSL2
- `booking-events` topic with 3 partitions
- Producer generating booking events
- Consumer reading events end-to-end

In progress:
- Rate-controlled load generation (ramp up to simulate spikes)
- Multi-worker consumer group
- Lag-based auto-scaler
- Metrics logging and benchmark plots

## Setup (native, no Docker)

Prerequisites: WSL2 + Ubuntu, Java 17, Python 3.

    # 1. Kafka (KRaft) — first-time storage format
    cd ~/kafka
    export KAFKA_HEAP_OPTS="-Xmx512m -Xms512m"
    KAFKA_CLUSTER_ID="$(bin/kafka-storage.sh random-uuid)"
    bin/kafka-storage.sh format --standalone -t "$KAFKA_CLUSTER_ID" -c config/server.properties

    # 2. Start the broker (leave running)
    bin/kafka-server-start.sh config/server.properties

    # 3. Create the topic (new terminal)
    bin/kafka-topics.sh --create --topic booking-events \
      --partitions 3 --replication-factor 1 --bootstrap-server localhost:9092

    # 4. Python env + run
    cd ~/realtime-event-processing-system
    python3 -m venv venv && source venv/bin/activate
    pip install kafka-python-ng psutil pandas matplotlib
    python consumer/consumer.py     # terminal A
    python producer/data_generator.py   # terminal B

## Future scope

- Containerize and deploy on AWS / GCP (this is where Docker/Kubernetes fit)
- Predictive (ML-based) auto-scaling instead of reactive thresholds
- Multi-tenant event categories and queues


## Measured throughput ceiling

Early load tests showed the producer cannot actually reach the 2000 msg/s
target on this machine. During a curve run, target rate climbed toward ~2000/s
but the achieved rate flattened at roughly 1100-1300 msg/s — the i3-8130U's
single-threaded limit for building and serializing JSON events one process at a
time. Nothing failed; the producer just couldn't send faster.

So I set the defaults to what the rig actually sustains: baseline 40 msg/s,
peak 1000 msg/s (a 25x surge). Target and achieved rates now track closely,
which gives clean benchmark curves instead of a clipped, flat peak.

This is why the "10x-100x spike" is framed as a simulated multiplier rather than
literal throughput. The system demonstrates scaling *behaviour* at rates this
hardware can push (~25x), and the report discusses extrapolation to higher
multiples. Reporting measured numbers rather than an unreachable target is the
honest way to present it, and the design (partitioning, consumer groups,
lag-based scaling) is what actually scales on bigger hardware.
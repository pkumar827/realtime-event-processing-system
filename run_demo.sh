#!/usr/bin/env bash
#
# End-to-end demo: runs a BASELINE (no scaling) pass, then an AUTO-SCALING pass
# against the same load, then generates comparison graphs. Keeps only the last
# 3 runs of CSVs + graphs.
#
# Each pass first resets the consumer group's offsets to "latest" so both passes
# start from a clean zero-lag state -- this makes the comparison graph aligned
# and honest (both start at lag 0).
#
# Prerequisites:
#   - Kafka running (bin/kafka-server-start.sh) with the booking-events topic
#   - virtualenv active, or it will try to activate ./venv
#
# Usage:
#   ./run_demo.sh            # short cycles, good for a live demo (~5-6 min)
#   ./run_demo.sh --full     # full-length cycles for report captures (~15 min)
#
set -euo pipefail

cd "$(dirname "$0")"

KAFKA_HOME="${KAFKA_HOME:-$HOME/kafka}"

# Activate venv if one exists and we're not already in it.
if [[ -z "${VIRTUAL_ENV:-}" && -f "venv/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source venv/bin/activate
fi

# Cycle timing: short by default, full-length with --full.
if [[ "${1:-}" == "--full" ]]; then
    PEAK=120; COOL=30; COUNT=3     # ~7.5 min per pass
else
    PEAK=60;  COOL=20; COUNT=2     # ~2.5 min per pass
fi

TS=$(date +%Y%m%d_%H%M%S)
RUN_DIR="metrics/runs/run_${TS}"
mkdir -p "${RUN_DIR}"
BASE_CSV="${RUN_DIR}/baseline.csv"
SCALER_CSV="${RUN_DIR}/scaler.csv"

echo "==================================================================="
echo " DEMO RUN ${TS}"
echo "   cycles: ${COUNT} x (${PEAK}s peak + ${COOL}s cool)"
echo "   output: ${RUN_DIR}"
echo "==================================================================="

reset_group() {
    # Reset consumer-group offsets to latest so the next pass starts at zero
    # lag. Requires no active members (true between passes).
    echo "  resetting consumer group offsets to latest..."
    "${KAFKA_HOME}/bin/kafka-consumer-groups.sh" \
        --bootstrap-server localhost:9092 \
        --group booking-workers \
        --topic booking-events \
        --reset-offsets --to-latest --execute >/dev/null 2>&1 \
        || echo "  (reset skipped -- group may not exist yet, which is fine)"
}

run_pass() {
    # $1 = label ; $2 = csv path ; $3 = extra scaler flag
    local label="$1" csv="$2" flag="${3:-}"
    echo ""
    echo "--- ${label} pass -------------------------------------------------"

    # Clean slate: reset offsets BEFORE any worker joins the group.
    reset_group

    # Start the scaler (background), give it a moment to warm up.
    python scaler/auto_scaler.py ${flag} --metrics-file "${csv}" &
    local scaler_pid=$!
    sleep 5

    # Run the producer in the foreground; it self-terminates after the cycles.
    python producer/data_generator.py --mode cycles \
        --cycle-peak "${PEAK}" --cycle-cool "${COOL}" --cycle-count "${COUNT}"

    # Let the last metrics flush, then stop the scaler cleanly.
    sleep 3
    kill -INT "${scaler_pid}"
    wait "${scaler_pid}" 2>/dev/null || true
    echo "--- ${label} pass done -> ${csv}"
}

run_pass "BASELINE (no scaling)" "${BASE_CSV}" "--no-scale"
echo ""
echo "Cooling down 10s before the auto-scaling pass..."
sleep 10
run_pass "AUTO-SCALING" "${SCALER_CSV}" ""

echo ""
echo "--- generating graphs --------------------------------------------"
python plot_metrics.py "${BASE_CSV}" "${SCALER_CSV}" --out-dir "${RUN_DIR}"

# Prune: keep only the newest 3 run directories.
echo ""
echo "--- pruning to last 3 runs ---------------------------------------"
cd metrics/runs
ls -1dt run_* 2>/dev/null | tail -n +4 | while read -r old; do
    echo "  removing old run: ${old}"
    rm -rf "${old}"
done
cd - >/dev/null

echo ""
echo "==================================================================="
echo " DEMO COMPLETE"
echo "   CSVs + graphs in: ${RUN_DIR}"
echo "   graphs: scaling.png, lag_compare.png, thrpt_compare.png"
echo "==================================================================="